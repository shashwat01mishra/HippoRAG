"""Follow-up analyses on the sealed grid records (offline; no API calls, no retrieval reruns).

Item 1 tests prediction item 4 (notes/prediction.md). Items 2 and 3 are EXPLORATORY: they were not in the prediction
and were chosen after the results were seen.

  1 interaction   (HippoRAG 2 correction@5 change n=1 -> 3) minus (dense change), per k and pooled, paired bootstrap
  2 baseline      k = 0: is the OLD fact among the 5 candidate facts; is its passage retrieved anyway.
    route         for passages in HippoRAG 2's top 5 whose fact was NOT a candidate (old passages at k = 0,
                  corrections at k >= 1): would the passage seed alone have done it (the passage is in the dense top 5,
                  and passage seeds are 0.05 x min-max dense), or did it need graph spread (dense rank > 5)?
                  Also the direct-teleport share of its PPR score, (1 - d) * seed / reset_total / score, d = 0.5:
                  the part of the score that is the passage's own seed arriving without any walk.
  3 asymmetry     HippoRAG 2 n=1 -> 3 change split by o' absent from the corpus vs present; for questions lost at
                  n = 3, old-minus-new PPR margin against degree(o) - degree(o') read from the cell's graph.pickle
                  (outputs/extension/grid_v5_20261109/cell_n3_k*_g*; read-only).
  4 rank          rank of the best correction per system at n = 1 and n = 3; other-hop gold passages in the top 5
CIs: 10,000 resamples of targets, seed 0, percentile 95 %.

    .venv/bin/python experiments/extension/followup.py --out analysis/grid_v5_final
"""
import argparse
import collections
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.analysis import load_records, restrict_to_final  # noqa: E402
from experiments.extension.common import DATA_DIR, REPO_ROOT, WORKING_DIR_NAME, text_processing  # noqa: E402
from experiments.extension.phase_b import KS, NS, RESULTS, boot_ci, rate  # noqa: E402
from src.hipporag.embedding_store import compute_mdhash_id  # noqa: E402

GRID_ROOT = REPO_ROOT / "outputs" / "extension" / "grid_v5_20261109"
DAMPING = 0.5   # src/hipporag/utils/config_utils.py:192-195; the grid used the default


def boot_diff_groups(a, b, n_boot=10000, seed=0):
    """Difference of means of two independent groups of targets (each resampled on its own)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    da = a[rng.integers(0, len(a), size=(n_boot, len(a)))].mean(axis=1)
    db = b[rng.integers(0, len(b), size=(n_boot, len(b)))].mean(axis=1)
    lo, hi = np.percentile(da - db, [2.5, 97.5])
    return {"mean": float(a.mean() - b.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "N": [len(a), len(b)]}


def spearman(x, y):
    if len(x) < 3:
        return None
    rank = lambda v: np.argsort(np.argsort(v)).astype(float)   # ties broken by order; fine for a descriptive rho
    from scipy.stats import spearmanr
    r, p = spearmanr(x, y)
    return {"rho": float(r), "p": float(p), "n": len(x)}


def route(rec, role):
    """For the best-ranked passage of `role` in the HippoRAG top 5: dense rank, direct-teleport share, seeds."""
    h = rec["hipporag"]["passages"]
    cands = [(p["rank"], c) for c, p in h.items() if p["role"] == role and p["rank"] <= 5]
    if not cands:
        return None
    _, c = min(cands)
    out = {"dense_rank": rec["dense"]["passages"][c]["rank"], "fallback_dense": rec["fallback_dense"]}
    if rec["stage_c"]:
        sc = rec["stage_c"]
        out["direct_share"] = (1 - DAMPING) * sc["seeds"][c] / sc["reset_total"] / h[c]["score"]
        out["subject_seeded"] = (sc["seeds"].get("s") or 0) > 0
        out["own_object_seeded"] = (sc["seeds"].get("o_prime" if role == "new" else "o") or 0) > 0
    return out


def route_summary(routes):
    ppr = [r for r in routes if not r["fallback_dense"]]
    by = lambda sel: [r for r in ppr if sel(r)]
    in5, out5 = by(lambda r: r["dense_rank"] <= 5), by(lambda r: r["dense_rank"] > 5)
    med = lambda rs, key: float(np.median([r[key] for r in rs])) if rs else None
    return {"records": len(routes), "dense_fallback": len(routes) - len(ppr),
            "also_in_dense_top5": len(in5), "not_in_dense_top5": len(out5),
            "dense_rank_6_20": len(by(lambda r: 6 <= r["dense_rank"] <= 20)), "dense_rank_gt_20": len(by(lambda r: r["dense_rank"] > 20)),
            "median_dense_rank_of_not_in_top5": med(out5, "dense_rank"),
            "direct_share_median": med(ppr, "direct_share"), "direct_share_max": max((r["direct_share"] for r in ppr), default=None),
            "direct_share_median_in_dense_top5": med(in5, "direct_share"), "direct_share_median_not_in_dense_top5": med(out5, "direct_share"),
            "subject_seeded": sum(r["subject_seeded"] for r in ppr), "own_object_seeded": sum(r["own_object_seeded"] for r in ppr)}


def compute(targets, records):
    nofix = {(tuple(r["cell"]), r["target_id"]): r for r in records if not r["fix"]}
    ids = sorted(targets)
    corr = lambda arm, n, k, t: float(nofix[((n, k), t)][arm]["correction_at5"])
    out = {"N": len(ids)}

    # ---- 1 interaction (prediction item 4) -----------------------------------------------------------
    inter = {"per_k": []}
    for k in KS:
        h = np.asarray([corr("hipporag", 3, k, t) - corr("hipporag", 1, k, t) for t in ids])
        d = np.asarray([corr("dense", 3, k, t) - corr("dense", 1, k, t) for t in ids])
        inter["per_k"].append({"k": k, "hipporag": boot_ci(h), "dense": boot_ci(d), "interaction": boot_ci(h - d)})
    h = np.asarray([np.mean([corr("hipporag", 3, k, t) - corr("hipporag", 1, k, t) for k in KS]) for t in ids])
    d = np.asarray([np.mean([corr("dense", 3, k, t) - corr("dense", 1, k, t) for k in KS]) for t in ids])
    inter["pooled"] = {"hipporag": boot_ci(h), "dense": boot_ci(d), "interaction": boot_ci(h - d),
                       "targets_hipporag_worse_at_n3": int((h < 0).sum()), "targets_hipporag_better_at_n3": int((h > 0).sum()),
                       "targets_dense_worse_at_n3": int((d < 0).sum()), "targets_dense_better_at_n3": int((d > 0).sum())}
    out["interaction"] = inter
    per_target_h = dict(zip(ids, h))

    # ---- 2 baseline and route (exploratory) ----------------------------------------------------------
    base = []
    for n in NS:
        rs = [nofix[((n, 0), t)] for t in ids]
        cand = [r for r in rs if r["flags"]["old_fact_in_candidates"]]
        non = [r for r in rs if not r["flags"]["old_fact_in_candidates"]]
        hit = lambda r, arm: r[arm]["contamination_at5"] > 0
        base.append({"n": n, "old_fact_candidate": rate(len(cand), len(rs)), "old_fact_kept": sum(r["flags"]["old_fact_kept"] for r in rs),
                     "old_passage_in_top5": rate(sum(hit(r, "hipporag") for r in rs), len(rs)),
                     "old_passage_in_top5_if_candidate": rate(sum(hit(r, "hipporag") for r in cand), len(cand)),
                     "old_passage_in_top5_if_not_candidate": rate(sum(hit(r, "hipporag") for r in non), len(non)),
                     "dense_old_passage_in_top5": rate(sum(hit(r, "dense") for r in rs), len(rs)),
                     "route_not_candidate": route_summary([x for x in (route(r, "old") for r in non if hit(r, "hipporag")) if x])})
    out["baseline_k0"] = base
    rt = []
    all_routes = []
    for n in NS:
        for k in KS:
            rs = [nofix[((n, k), t)] for t in ids]
            ok = [r for r in rs if r["hipporag"]["correction_at5"]]
            via_fact = [r for r in ok if r["flags"]["new_fact_in_candidates"]]
            routes = [x for x in (route(r, "new") for r in ok if not r["flags"]["new_fact_in_candidates"]) if x]
            all_routes += routes
            rt.append({"n": n, "k": k, "corrections_in_top5": len(ok), "new_fact_was_candidate": len(via_fact),
                       "new_fact_kept": sum(r["flags"]["new_fact_kept"] for r in ok), **route_summary(routes)})
    out["route_corrections"] = rt
    out["route_corrections_pooled"] = {"corrections_in_top5": sum(e["corrections_in_top5"] for e in rt),
                                       "new_fact_was_candidate": sum(e["new_fact_was_candidate"] for e in rt),
                                       "new_fact_kept": sum(e["new_fact_kept"] for e in rt), **route_summary(all_routes)}

    # ---- 3 asymmetry (exploratory) -------------------------------------------------------------------
    absent = [t for t in ids if targets[t]["freq_oprime_graph"] == 0]
    present = [t for t in ids if targets[t]["freq_oprime_graph"] > 0]
    dense_change = dict(zip(ids, d))
    asym = {"o_prime_absent": {"hipporag_change": boot_ci([per_target_h[t] for t in absent]), "dense_change": boot_ci([dense_change[t] for t in absent]),
                               "n1_correction_at5": float(np.mean([np.mean([corr("hipporag", 1, k, t) for k in KS]) for t in absent])),
                               "n3_correction_at5": float(np.mean([np.mean([corr("hipporag", 3, k, t) for k in KS]) for t in absent]))},
            "o_prime_present": {"hipporag_change": boot_ci([per_target_h[t] for t in present]), "dense_change": boot_ci([dense_change[t] for t in present]),
                                "n1_correction_at5": float(np.mean([np.mean([corr("hipporag", 1, k, t) for k in KS]) for t in present])),
                                "n3_correction_at5": float(np.mean([np.mean([corr("hipporag", 3, k, t) for k in KS]) for t in present]))},
            "absent_minus_present": boot_diff_groups([per_target_h[t] for t in absent], [per_target_h[t] for t in present])}
    key = lambda name: compute_mdhash_id(text_processing(name), prefix="entity-")
    lost_rows, graphs = [], {}
    for k in KS:
        for t in ids:
            a, b = nofix[((1, k), t)], nofix[((3, k), t)]
            if not (a["hipporag"]["correction_at5"] and not b["hipporag"]["correction_at5"]):
                continue
            g_id = b.get("group", 0)
            if (k, g_id) not in graphs:
                path = GRID_ROOT / f"cell_n3_k{k}_g{g_id}_musique" / WORKING_DIR_NAME / "graph.pickle"
                g = pickle.loads(path.read_bytes())
                graphs[(k, g_id)] = (g, {n: i for i, n in enumerate(g.vs["name"])})
            g, idx = graphs[(k, g_id)]
            tg = targets[t]
            deg = lambda name: g.degree(idx[key(name)]) if key(name) in idx else None
            strength = lambda name: float(g.strength(idx[key(name)], weights="weight")) if key(name) in idx else None
            h3 = b["hipporag"]
            lost_rows.append({"target_id": t, "k": k, "o": tg["o"], "o_prime": tg["o_prime"], "o_prime_absent": tg["freq_oprime_graph"] == 0,
                              "deg_o": deg(tg["o"]), "deg_o_prime": deg(tg["o_prime"]),
                              "strength_o": strength(tg["o"]), "strength_o_prime": strength(tg["o_prime"]),
                              "margin_old_minus_new": h3["best_old"] - h3["best_new"],
                              "relative_margin": (h3["best_old"] - h3["best_new"]) / max(h3["best_old"], h3["best_new"]),
                              "cosine_margin_old_minus_new": b["dense"]["best_old"] - b["dense"]["best_new"],
                              "old_in_top5": h3["contamination_at5"],
                              "best_new_rank": min(p["rank"] for p in h3["passages"].values() if p["role"] == "new")})
    ok = [r for r in lost_rows if r["deg_o"] is not None and r["deg_o_prime"] is not None]
    dd = [r["deg_o"] - r["deg_o_prime"] for r in ok]
    asym["lost_at_n3"] = {
        "records": len(lost_rows), "targets": len({r["target_id"] for r in lost_rows}), "with_both_nodes": len(ok),
        "old_outranks_new": sum(r["margin_old_minus_new"] > 0 for r in lost_rows),
        "deg_o_gt_deg_o_prime": sum(x > 0 for x in dd), "deg_equal": sum(x == 0 for x in dd), "deg_o_lt_deg_o_prime": sum(x < 0 for x in dd),
        "median_degree_difference": float(np.median(dd)) if dd else None,
        "spearman_margin_vs_degree_difference": spearman(dd, [r["margin_old_minus_new"] for r in ok]),
        "spearman_relative_margin_vs_degree_difference": spearman(dd, [r["relative_margin"] for r in ok]),
        "spearman_margin_vs_cosine_margin": spearman([r["cosine_margin_old_minus_new"] for r in lost_rows], [r["margin_old_minus_new"] for r in lost_rows]),
        "sign_agreement_margin_and_degree_difference": rate(sum((r["margin_old_minus_new"] > 0) == (r["deg_o"] - r["deg_o_prime"] > 0) for r in ok
                                                                 if r["deg_o"] != r["deg_o_prime"]), sum(r["deg_o"] != r["deg_o_prime"] for r in ok)),
        "o_prime_absent": sum(r["o_prime_absent"] for r in lost_rows), "rows": lost_rows}
    out["asymmetry"] = asym

    # ---- 4 rank of the correction and other-hop passages (exploratory) -------------------------------
    BINS = ("1", "2", "3", "4", "5", "6-10", ">10")
    binof = lambda r: str(r) if r <= 5 else ("6-10" if r <= 10 else ">10")
    best = lambda rec, arm: min(p["rank"] for p in rec[arm]["passages"].values() if p["role"] == "new")
    other = lambda rec, arm: sum(x["role"] == "gold_other" for x in rec[arm]["top5"])
    rk = {}
    for arm in ("hipporag", "dense"):
        e = {}
        for n in NS:
            ranks = [best(nofix[((n, k), t)], arm) for k in KS for t in ids]
            c = collections.Counter(binof(r) for r in ranks)
            in5 = [r for r in ranks if r <= 5]
            e[f"n{n}"] = {"records": len(ranks), "bins": {b: c.get(b, 0) for b in BINS}, "in_top5": len(in5),
                          "of_in_top5_rank_1_2": rate(sum(r <= 2 for r in in5), len(in5)),
                          "of_in_top5_rank_4_5": rate(sum(r >= 4 for r in in5), len(in5)),
                          "median_rank_in_top5": float(np.median(in5)) if in5 else None}
        # what happens at n = 3 to corrections that were in the top 5 at n = 1, by their n = 1 rank
        trans = {}
        shifts = []
        for b in ("1", "2", "3", "4", "5"):
            pairs = [(best(nofix[((1, k), t)], arm), best(nofix[((3, k), t)], arm)) for k in KS for t in ids]
            sel = [(a, c3) for a, c3 in pairs if str(a) == b]
            trans[b] = {"at_n1": len(sel), "lost_at_n3": sum(c3 > 5 for _, c3 in sel)}
            shifts += [c3 - a for a, c3 in sel]
        e["by_n1_rank"] = trans
        e["rank_shift_n1_to_n3_for_in_top5_at_n1"] = {"median": float(np.median(shifts)), "mean": float(np.mean(shifts)),
                                                      "unchanged": sum(x == 0 for x in shifts), "down_1_or_2": sum(1 <= x <= 2 for x in shifts),
                                                      "down_3_plus": sum(x >= 3 for x in shifts), "up": sum(x < 0 for x in shifts), "records": len(shifts)}
        # other-hop gold passages in the top 5 at n = 1
        oth_all = [other(nofix[((1, k), t)], arm) for k in KS for t in ids]
        oth_in = [other(nofix[((1, k), t)], arm) for k in KS for t in ids if best(nofix[((1, k), t)], arm) <= 5]
        old_in = [nofix[((1, k), t)][arm]["contamination_at5"] for k in KS for t in ids if best(nofix[((1, k), t)], arm) <= 5]
        new_in = [sum(x["role"] == "new" for x in nofix[((1, k), t)][arm]["top5"]) for k in KS for t in ids if best(nofix[((1, k), t)], arm) <= 5]
        e["other_hop_gold_in_top5_n1"] = {"mean_all_records": float(np.mean(oth_all)), "total_slots_all_records": int(sum(oth_all)),
                                          "records_with_at_least_one": rate(sum(x > 0 for x in oth_all), len(oth_all)),
                                          "mean_when_correction_in_top5": float(np.mean(oth_in)), "total_slots_when_correction_in_top5": int(sum(oth_in)),
                                          "records_with_at_least_one_when_correction_in_top5": rate(sum(x > 0 for x in oth_in), len(oth_in)),
                                          "mean_old_slots_when_correction_in_top5": float(np.mean(old_in)),
                                          "mean_correction_slots_when_correction_in_top5": float(np.mean(new_in))}
        # at n = 1, correction in the top 5: is an other-hop gold passage ranked ABOVE the correction?
        above = []
        for k in KS:
            for t in ids:
                rec = nofix[((1, k), t)]
                b = best(rec, arm)
                if b <= 5:
                    above.append(sum(x["role"] == "gold_other" for x in rec[arm]["top5"][:b - 1]))
        e["other_hop_ranked_above_correction_n1"] = {"records": len(above), "with_at_least_one": sum(x > 0 for x in above), "mean": float(np.mean(above))}
        rk[arm] = e
    # the lost-at-n3 HippoRAG records: where was the correction at n = 1, and how many other-hop passages were in the top 5
    lost = [(nofix[((1, k), t)], nofix[((3, k), t)]) for k in KS for t in ids
            if nofix[((1, k), t)]["hipporag"]["correction_at5"] and not nofix[((3, k), t)]["hipporag"]["correction_at5"]]
    kept = [(nofix[((1, k), t)], nofix[((3, k), t)]) for k in KS for t in ids
            if nofix[((1, k), t)]["hipporag"]["correction_at5"] and nofix[((3, k), t)]["hipporag"]["correction_at5"]]
    desc = lambda prs: {"records": len(prs), "n1_rank_bins": {b: sum(binof(best(a, "hipporag")) == b for a, _ in prs) for b in ("1", "2", "3", "4", "5")},
                        "n1_rank_4_5": sum(best(a, "hipporag") >= 4 for a, _ in prs),
                        "mean_other_hop_in_top5_n1": float(np.mean([other(a, "hipporag") for a, _ in prs])),
                        "with_other_hop_in_top5_n1": sum(other(a, "hipporag") > 0 for a, _ in prs),
                        "dense_has_correction_in_top5_n1": sum(bool(a["dense"]["correction_at5"]) for a, _ in prs),
                        "dense_has_correction_in_top5_n3": sum(bool(b3["dense"]["correction_at5"]) for _, b3 in prs)}
    rk["hipporag_lost_at_n3"] = desc(lost)
    rk["hipporag_kept_at_n3"] = desc(kept)
    out["rank"] = rk
    return out


def pct(r):
    return "-" if r["rate"] is None else f"{r['num']}/{r['den']} ({r['rate']:.0%})"


def ci(b):
    return f"{b['mean'] * 100:+.1f} [{b['ci_lo'] * 100:+.1f}, {b['ci_hi'] * 100:+.1f}]"


def sp(s):
    return "-" if s is None else f"ρ = {s['rho']:+.2f} (p = {s['p']:.2f}, n = {s['n']})"


def fmt(v, f=".0%"):
    return "-" if v is None else format(v, f)


def markdown(o):
    i = o["interaction"]
    L = ["# Follow-up analyses (existing records only)", "",
         f"N = {o['N']} swaps. Source: `results/extension/grid_v5_20261109/*.jsonl` and, for node degrees, the cell graphs under "
         "`outputs/extension/grid_v5_20261109/`, via `experiments/extension/followup.py`; full numbers in `followup.json`. "
         "CIs: 10,000 resamples of targets, seed 0, percentile 95 %.", "",
         "## 1. Interaction: is the graph more repetition-sensitive than dense? (tests prediction item 4)", "",
         "Change in correction@5 from n = 1 to n = 3, in points; interaction = HippoRAG 2 change − dense change.", "",
         "| k | HippoRAG 2 | dense | interaction |", "|---|---|---|---|"]
    L += [f"| {e['k']} | {ci(e['hipporag'])} | {ci(e['dense'])} | {ci(e['interaction'])} |" for e in i["per_k"]]
    p = i["pooled"]
    L += [f"| pooled over k | {ci(p['hipporag'])} | {ci(p['dense'])} | **{ci(p['interaction'])}** |", "",
          f"Per question (pooled over k): HippoRAG 2 is worse at n = 3 for {p['targets_hipporag_worse_at_n3']} questions and better for "
          f"{p['targets_hipporag_better_at_n3']}; dense is worse for {p['targets_dense_worse_at_n3']} and better for {p['targets_dense_better_at_n3']}.", "",
          "## 2. EXPLORATORY: baseline for the old fact, and the route into the top 5", "",
          "### k = 0 (no correction): the old fact and its passage", "",
          "| n | old fact among the 5 candidates | old passage in HippoRAG 2 top 5 | ... if the fact is a candidate | ... if it is not | old passage in dense top 5 |",
          "|---|---|---|---|---|---|"]
    for e in o["baseline_k0"]:
        L.append(f"| {e['n']} | {pct(e['old_fact_candidate'])} | {pct(e['old_passage_in_top5'])} | {pct(e['old_passage_in_top5_if_candidate'])} | "
                 f"{pct(e['old_passage_in_top5_if_not_candidate'])} | {pct(e['dense_old_passage_in_top5'])} |")
    hdr = ["| cell | in top 5 | fact was a candidate | not a candidate | of those: dense fallback | also in dense top 5 | not in dense top 5 (rank 6–20 / > 20) | "
           "direct-teleport share of PPR score, median (in dense top 5 / not) | subject entity seeded | own object seeded |", "|---|---|---|---|---|---|---|---|---|---|"]
    row = lambda name, total, cand, e: (
        f"| {name} | {total} | {cand} | {e['records']} | {e['dense_fallback']} | {e['also_in_dense_top5']} | "
        f"{e['not_in_dense_top5']} ({e['dense_rank_6_20']} / {e['dense_rank_gt_20']}) | {fmt(e['direct_share_median'], '.1%')} "
        f"({fmt(e['direct_share_median_in_dense_top5'], '.1%')} / {fmt(e['direct_share_median_not_in_dense_top5'], '.1%')}) | "
        f"{e['subject_seeded']} | {e['own_object_seeded']} |")
    L += ["", "### Route into HippoRAG 2's top 5 when the passage's fact was not a candidate", "",
          "\"Also in dense top 5\": the passage seed alone (0.05 × min-max dense) ranks it in the top 5. \"Not in dense top 5\": it needed graph spread from other seeds. "
          "Direct-teleport share = (1 − d) · seed / reset total / PPR score with d = 0.5: the part of the passage's score that is its own seed with no walk.", ""] + hdr
    for e in o["baseline_k0"]:
        r = e["route_not_candidate"]
        L.append(row(f"old passage, n = {e['n']}, k = 0", e["old_passage_in_top5"]["num"], e["old_passage_in_top5_if_candidate"]["num"], r))
    for e in o["route_corrections"]:
        L.append(row(f"correction, n = {e['n']}, k = {e['k']}", e["corrections_in_top5"], e["new_fact_was_candidate"], e))
    e = o["route_corrections_pooled"]
    L.append(row("**correction, all 8 cells**", e["corrections_in_top5"], e["new_fact_was_candidate"], e))
    a = o["asymmetry"]
    L += ["", "## 3. EXPLORATORY: asymmetry", "",
          "### HippoRAG 2's n = 1 → 3 change by whether o′ already exists in the corpus (points, pooled over k)", "",
          "| o′ | N | correction@5 at n = 1 | at n = 3 | HippoRAG 2 change | dense change |", "|---|---|---|---|---|---|"]
    for lab, name in (("o_prime_absent", "absent (new node)"), ("o_prime_present", "present")):
        x = a[lab]
        L.append(f"| {name} | {x['hipporag_change']['N']} | {x['n1_correction_at5']:.1%} | {x['n3_correction_at5']:.1%} | {ci(x['hipporag_change'])} | {ci(x['dense_change'])} |")
    L += ["", f"Absent minus present: {ci(a['absent_minus_present'])} points.", ""]
    lo = a["lost_at_n3"]
    L += ["### Questions HippoRAG 2 retrieves at n = 1 and loses at n = 3", "",
          f"{lo['records']} records from {lo['targets']} questions (k = 1, 2, 3, 5). The old passage outranks the correction in {lo['old_outranks_new']}. "
          f"o′ is absent from the base corpus in {lo['o_prime_absent']}. Node degree in the n = 3 cell's graph: degree(o) > degree(o′) in {lo['deg_o_gt_deg_o_prime']}, "
          f"equal in {lo['deg_equal']}, smaller in {lo['deg_o_lt_deg_o_prime']}; median difference {lo['median_degree_difference']:+.0f}. "
          f"Among records with unequal degrees, the sign of the PPR margin matches the sign of the degree difference in {pct(lo['sign_agreement_margin_and_degree_difference'])}.", "",
          f"- old-minus-new PPR margin vs degree(o) − degree(o′): {sp(lo['spearman_margin_vs_degree_difference'])}",
          f"- relative margin vs degree difference: {sp(lo['spearman_relative_margin_vs_degree_difference'])}",
          f"- PPR margin vs dense-cosine margin (old − new): {sp(lo['spearman_margin_vs_cosine_margin'])}", "",
          "| question | k | o → o′ | o′ absent | degree o | degree o′ | PPR margin old − new | relative | cosine margin old − new | old in top 5 | best correction rank |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(lo["rows"], key=lambda r: (r["target_id"], r["k"])):
        L.append(f"| {r['target_id']} | {r['k']} | {r['o']} → {r['o_prime']} | {'yes' if r['o_prime_absent'] else 'no'} | {r['deg_o']} | {r['deg_o_prime']} | "
                 f"{r['margin_old_minus_new']:+.2e} | {r['relative_margin']:+.1%} | {r['cosine_margin_old_minus_new']:+.4f} | {r['old_in_top5']} | {r['best_new_rank']} |")
    rk = o["rank"]
    BINS = ("1", "2", "3", "4", "5", "6-10", ">10")
    L += ["", "## 4. EXPLORATORY: where the correction sits, and what else is in the top 5", "",
          "Rank of the best-ranked correction, pooled over k = 1, 2, 3, 5 (300 records per row).", "",
          "| system | n | " + " | ".join(BINS) + " | in top 5 | of those at rank 1–2 | at rank 4–5 | median rank in top 5 |", "|---|---|" + "---|" * (len(BINS) + 4)]
    for arm, name in (("hipporag", "HippoRAG 2"), ("dense", "dense")):
        for n in (1, 3):
            e = rk[arm][f"n{n}"]
            L.append(f"| {name} | {n} | " + " | ".join(str(e["bins"][b]) for b in BINS) + f" | {e['in_top5']} | {pct(e['of_in_top5_rank_1_2'])} | "
                     f"{pct(e['of_in_top5_rank_4_5'])} | {e['median_rank_in_top5']:.0f} |")
    L += ["", "Corrections in the top 5 at n = 1: how many are lost at n = 3, by their n = 1 rank.", "",
          "| system | rank 1 | rank 2 | rank 3 | rank 4 | rank 5 | rank shift n = 1 → 3: unchanged / down 1–2 / down ≥ 3 / up (median) |", "|---|---|---|---|---|---|---|"]
    for arm, name in (("hipporag", "HippoRAG 2"), ("dense", "dense")):
        t, sh = rk[arm]["by_n1_rank"], rk[arm]["rank_shift_n1_to_n3_for_in_top5_at_n1"]
        L.append(f"| {name} | " + " | ".join(f"{t[b]['lost_at_n3']} of {t[b]['at_n1']}" for b in ("1", "2", "3", "4", "5")) +
                 f" | {sh['unchanged']} / {sh['down_1_or_2']} / {sh['down_3_plus']} / {sh['up']} ({sh['median']:+.0f}) |")
    L += ["", "Top-5 slots at n = 1 (pooled over k).", "",
          "| system | other-hop gold slots, all 300 records (mean per record) | records with ≥ 1 | when the correction is in the top 5: other-hop slots (mean) | records with ≥ 1 | correction slots (mean) | old-passage slots (mean) | an other-hop passage ranked above the correction |",
          "|---|---|---|---|---|---|---|---|"]
    for arm, name in (("hipporag", "HippoRAG 2"), ("dense", "dense")):
        e, ab = rk[arm]["other_hop_gold_in_top5_n1"], rk[arm]["other_hop_ranked_above_correction_n1"]
        L.append(f"| {name} | {e['total_slots_all_records']} ({e['mean_all_records']:.2f}) | {pct(e['records_with_at_least_one'])} | "
                 f"{e['total_slots_when_correction_in_top5']} ({e['mean_when_correction_in_top5']:.2f}) | {pct(e['records_with_at_least_one_when_correction_in_top5'])} | "
                 f"{e['mean_correction_slots_when_correction_in_top5']:.2f} | {e['mean_old_slots_when_correction_in_top5']:.2f} | {ab['with_at_least_one']} of {ab['records']} |")
    L += ["", "HippoRAG 2 corrections in the top 5 at n = 1, split by what happens at n = 3.", "",
          "| | records | n = 1 rank 1 / 2 / 3 / 4 / 5 | at rank 4–5 | with an other-hop passage in the top 5 at n = 1 (mean slots) | dense has the correction at n = 1 | at n = 3 |",
          "|---|---|---|---|---|---|---|"]
    for lab, name in (("hipporag_lost_at_n3", "lost at n = 3"), ("hipporag_kept_at_n3", "kept at n = 3")):
        e = rk[lab]
        L.append(f"| {name} | {e['records']} | " + " / ".join(str(e["n1_rank_bins"][b]) for b in ("1", "2", "3", "4", "5")) +
                 f" | {e['n1_rank_4_5']} | {e['with_other_hop_in_top5_n1']} ({e['mean_other_hop_in_top5_n1']:.2f}) | "
                 f"{e['dense_has_correction_in_top5_n1']} | {e['dense_has_correction_in_top5_n3']} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    targets = {json.loads(l)["target_id"]: json.loads(l) for l in (DATA_DIR / "targets_v5.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    targets, records = restrict_to_final(targets, load_records(RESULTS), DATA_DIR / "targets_final.jsonl")
    o = compute(targets, records)
    out = Path(a.out)
    (out / "followup.json").write_text(json.dumps(o, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "followup.md").write_text(markdown(o), encoding="utf-8")
    print(f"N = {o['N']}; wrote {out}/followup.json and followup.md")


if __name__ == "__main__":
    main()
