"""Phase B supplement to analysis.py (offline): the numbers the prediction items need that analysis.py does not print.

Reads the sealed grid records, restricted to targets_final.jsonl (optionally minus some review rows), and writes
<out>/phase_b.json and <out>/phase_b.md:
  funnel        per cell, no-fix arm: old/new fact among the top-5 candidates (stage A), kept by the filter (stage B),
                both kept, dense fallback; correction@5 split by whether the new fact was a candidate
  filter        filter keep rate of the new fact given it was a candidate, overall and by model_knows_o (items 1, 7)
  both_seeded   records where the filter kept both facts: PPR outcome at each tolerance, and whether the sign of the
                PPR margin equals the sign of the dense-cosine margin (item 2)
  n_effect      correction@5 change from n = 1 to n = 3 per k, HippoRAG vs dense, with a paired bootstrap CI of the
                difference of changes (item 4)
  fix           fix minus no-fix: correction@5, records where the fix fired, what changed there; recall of the
                question's other gold passages (unchanged facts) in the top 5; top-5 identity at k = 0 (item 5)
  pooled        correction@5 pooled over the 8 k >= 1 cells per arm, with a bootstrap CI over targets (headline)
  long_context  reader answer labels at the four corners
All CIs: 10,000 resamples of targets, seed 0, percentile 95 %.

    .venv/bin/python experiments/extension/phase_b.py --out analysis/grid_v5_final
    .venv/bin/python experiments/extension/phase_b.py --out analysis/grid_v5_final_minus_specialist --drop_rows 19,25,29,45,91,100,109,114
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.analysis import TOLERANCES, load_records, restrict_to_final  # noqa: E402
from experiments.extension.attrib_rag import outranks_old  # noqa: E402
from experiments.extension.common import DATA_DIR, DATASET_DIR, REPO_ROOT  # noqa: E402

RESULTS = REPO_ROOT / "results" / "extension" / "grid_v5_20261109"
KS = (1, 2, 3, 5)
NS = (1, 3)


def boot_ci(values, n_boot=10000, seed=0):
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    b = v[rng.integers(0, len(v), size=(n_boot, len(v)))].mean(axis=1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return {"mean": float(v.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "N": int(len(v))}


def rate(num, den):
    return {"num": int(num), "den": int(den), "rate": (num / den if den else None)}


def row_ids(review_path):
    out = {}
    for line in Path(review_path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| [yn] \| (\d+) \| (\S+) \|", line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def compute(targets, records, lc_rows, samples):
    nofix = {(tuple(r["cell"]), r["target_id"]): r for r in records if not r["fix"]}
    fix = {(tuple(r["cell"]), r["target_id"]): r for r in records if r["fix"]}
    ids = sorted(targets)
    knows = {t: bool(targets[t]["model_knows_o"]) for t in ids}
    out = {"N": len(ids), "model_knows_o": {"yes": sum(knows.values()), "no": len(ids) - sum(knows.values())}}

    # ---- funnel ------------------------------------------------------------------------------------
    funnel = []
    for n in NS:
        for k in (0,) + KS:
            rs = [nofix[((n, k), t)] for t in ids]
            f = lambda key: sum(r["flags"][key] for r in rs)
            e = {"n": n, "k": k, "N": len(rs), "fallback_dense": sum(r["fallback_dense"] for r in rs),
                 "old_in_candidates": f("old_fact_in_candidates"), "new_in_candidates": f("new_fact_in_candidates"),
                 "old_kept": f("old_fact_kept"), "new_kept": f("new_fact_kept"),
                 "both_kept": sum(r["flags"]["old_fact_kept"] and r["flags"]["new_fact_kept"] for r in rs),
                 "mean_facts_kept": float(np.mean([len(r["stage_b"]["kept"]) for r in rs]))}
            if k:
                cand = [r for r in rs if r["flags"]["new_fact_in_candidates"]]
                non = [r for r in rs if not r["flags"]["new_fact_in_candidates"]]
                e["correction_at5_if_new_candidate"] = rate(sum(r["hipporag"]["correction_at5"] for r in cand), len(cand))
                e["correction_at5_if_not_candidate"] = rate(sum(r["hipporag"]["correction_at5"] for r in non), len(non))
                e["dense_correction_at5_if_not_candidate"] = rate(sum(r["dense"]["correction_at5"] for r in non), len(non))
            funnel.append(e)
    out["funnel"] = funnel

    # ---- filter keep rates (items 1, 6, 7) -----------------------------------------------------------
    filt = []
    for n in NS:
        for k in KS:
            rs = [(t, nofix[((n, k), t)]) for t in ids]
            cand = [(t, r) for t, r in rs if r["flags"]["new_fact_in_candidates"]]
            e = {"n": n, "k": k,
                 "new_kept_given_candidate": rate(sum(r["flags"]["new_fact_kept"] for _, r in cand), len(cand)),
                 "new_kept_of_all_questions": rate(sum(r["flags"]["new_fact_kept"] for _, r in rs), len(rs))}
            ocand = [(t, r) for t, r in rs if r["flags"]["old_fact_in_candidates"]]
            e["old_kept_given_candidate"] = rate(sum(r["flags"]["old_fact_kept"] for _, r in ocand), len(ocand))
            for lab, val in (("knows_yes", True), ("knows_no", False)):
                c = [(t, r) for t, r in cand if knows[t] == val]
                e[f"new_kept_given_candidate_{lab}"] = rate(sum(r["flags"]["new_fact_kept"] for _, r in c), len(c))
            filt.append(e)
    out["filter"] = filt
    # pooled over the 8 k >= 1 cells; per-target rates so the CI resamples targets
    per_t = collections.defaultdict(lambda: [0, 0])
    for n in NS:
        for k in KS:
            for t in ids:
                r = nofix[((n, k), t)]
                if r["flags"]["new_fact_in_candidates"]:
                    per_t[t][1] += 1
                    per_t[t][0] += r["flags"]["new_fact_kept"]
    pooled = {}
    for lab, sel in (("all", lambda t: True), ("knows_yes", lambda t: knows[t]), ("knows_no", lambda t: not knows[t])):
        ts = [t for t in per_t if sel(t)]
        pooled[lab] = {"records": rate(sum(per_t[t][0] for t in ts), sum(per_t[t][1] for t in ts)),
                       "targets_with_a_candidate_record": len(ts),
                       "mean_of_per_target_rates": boot_ci([per_t[t][0] / per_t[t][1] for t in ts]) if ts else None}
    out["filter_pooled_given_candidate"] = pooled

    # ---- both kept: tie and dense agreement (item 2) -------------------------------------------------
    both = [r for (cell, t), r in nofix.items() if t in targets and cell[1] > 0
            and r["flags"]["old_fact_kept"] and r["flags"]["new_fact_kept"] and not r["fallback_dense"]]
    e = {"records": len(both), "targets": len({r["target_id"] for r in both})}
    for tol in TOLERANCES:
        c = collections.Counter(outranks_old(r["hipporag"]["best_new"], r["hipporag"]["best_old"], tol) for r in both)
        e[f"outcome@{tol:g}"] = {o: c.get(o, 0) for o in ("outranks", "near_tie", "loses")}
    agree = sum(np.sign(r["hipporag"]["best_new"] - r["hipporag"]["best_old"]) ==
                np.sign(r["dense"]["best_new"] - r["dense"]["best_old"]) for r in both)
    e["ppr_margin_sign_equals_cosine_margin_sign"] = rate(agree, len(both))
    rel = [abs(r["hipporag"]["best_new"] - r["hipporag"]["best_old"]) / max(r["hipporag"]["best_new"], r["hipporag"]["best_old"]) for r in both]
    e["relative_ppr_margin_median"] = float(np.median(rel)) if rel else None
    e["correction_at5"] = rate(sum(r["hipporag"]["correction_at5"] for r in both), len(both))
    e["seed_o_prime_gt_0"] = rate(sum((r["stage_c"]["seeds"].get("o_prime") or 0) > 0 for r in both), len(both))
    # the same agreement over all k >= 1 no-fix records (not only both-kept)
    allr = [r for (cell, t), r in nofix.items() if t in targets and cell[1] > 0]
    e["all_records_sign_agreement"] = rate(sum(np.sign(r["hipporag"]["best_new"] - r["hipporag"]["best_old"]) ==
                                               np.sign(r["dense"]["best_new"] - r["dense"]["best_old"]) for r in allr), len(allr))
    out["both_seeded"] = e

    # ---- n effect (item 4) ---------------------------------------------------------------------------
    n_eff = []
    for k in KS:
        h = [nofix[((3, k), t)]["hipporag"]["correction_at5"] - nofix[((1, k), t)]["hipporag"]["correction_at5"] for t in ids]
        d = [nofix[((3, k), t)]["dense"]["correction_at5"] - nofix[((1, k), t)]["dense"]["correction_at5"] for t in ids]
        n_eff.append({"k": k, "hipporag_change_n1_to_n3": boot_ci(h), "dense_change_n1_to_n3": boot_ci(d),
                      "hipporag_minus_dense_change": boot_ci(np.asarray(h) - np.asarray(d))})
    hp = [np.mean([nofix[((3, k), t)]["hipporag"]["correction_at5"] - nofix[((1, k), t)]["hipporag"]["correction_at5"] for k in KS]) for t in ids]
    dp = [np.mean([nofix[((3, k), t)]["dense"]["correction_at5"] - nofix[((1, k), t)]["dense"]["correction_at5"] for k in KS]) for t in ids]
    out["n_effect"] = {"per_k": n_eff, "pooled_over_k": {"hipporag_change": boot_ci(hp), "dense_change": boot_ci(dp),
                                                         "hipporag_minus_dense_change": boot_ci(np.asarray(hp) - np.asarray(dp))}}

    # ---- pooled headline -----------------------------------------------------------------------------
    cells = [(n, k) for n in NS for k in KS]
    arm_val = {"dense": lambda c, t: nofix[(c, t)]["dense"]["correction_at5"],
               "hipporag": lambda c, t: nofix[(c, t)]["hipporag"]["correction_at5"],
               "hipporag_fix": lambda c, t: fix[(c, t)]["hipporag"]["correction_at5"]}
    pooled = {}
    for scope, cs in (("all_k>=1_cells", cells), ("n=1", [c for c in cells if c[0] == 1]), ("n=3", [c for c in cells if c[0] == 3])):
        per = {a: np.asarray([np.mean([f(c, t) for c in cs]) for t in ids]) for a, f in arm_val.items()}
        pooled[scope] = {**{a: boot_ci(v) for a, v in per.items()},
                         "hipporag_minus_dense": boot_ci(per["hipporag"] - per["dense"]),
                         "fix_minus_hipporag": boot_ci(per["hipporag_fix"] - per["hipporag"])}
    out["pooled_correction_at5"] = pooled
    cont = {}
    for scope, cs in (("k=0", [(1, 0), (3, 0)]), ("k>=1", cells)):
        per = {"dense": np.asarray([np.mean([nofix[(c, t)]["dense"]["contamination_at5"] for c in cs]) for t in ids]),
               "hipporag": np.asarray([np.mean([nofix[(c, t)]["hipporag"]["contamination_at5"] for c in cs]) for t in ids]),
               "hipporag_fix": np.asarray([np.mean([fix[(c, t)]["hipporag"]["contamination_at5"] for c in cs]) for t in ids])}
        cont[scope] = {**{a: boot_ci(v) for a, v in per.items()}, "hipporag_minus_dense": boot_ci(per["hipporag"] - per["dense"]),
                       "fix_minus_hipporag": boot_ci(per["hipporag_fix"] - per["hipporag"])}
    out["pooled_contamination_at5"] = cont

    # ---- fix (item 5) --------------------------------------------------------------------------------
    n_other = {t: sum(p["is_supporting"] for p in samples[t]["paragraphs"]) - 1 for t in ids}
    other_recall = lambda r, t: sum(x["role"] == "gold_other" for x in r["hipporag"]["top5"]) / n_other[t]
    fx = []
    for n in NS:
        for k in (0,) + KS:
            pairs = [(t, nofix[((n, k), t)], fix[((n, k), t)]) for t in ids]
            fired = [(t, a, b) for t, a, b in pairs if b["fix_trace"]["dropped"]]
            e = {"n": n, "k": k, "fix_fired_records": len(fired),
                 "top5_identical_records": sum([x["chunk"] for x in a["hipporag"]["top5"]] == [x["chunk"] for x in b["hipporag"]["top5"]] for _, a, b in pairs),
                 "other_gold_recall_at5_nofix": float(np.mean([other_recall(a, t) for t, a, _ in pairs])),
                 "other_gold_recall_at5_fix": float(np.mean([other_recall(b, t) for t, _, b in pairs])),
                 "other_gold_recall_changed_records": sum(other_recall(a, t) != other_recall(b, t) for t, a, b in pairs)}
            if k:
                e["correction_at5_nofix"] = float(np.mean([a["hipporag"]["correction_at5"] for _, a, _ in pairs]))
                e["correction_at5_fix"] = float(np.mean([b["hipporag"]["correction_at5"] for _, _, b in pairs]))
                e["where_fired"] = {
                    "correction_at5_nofix": sum(a["hipporag"]["correction_at5"] for _, a, _ in fired),
                    "correction_at5_fix": sum(b["hipporag"]["correction_at5"] for _, _, b in fired),
                    "outranks@0_nofix": sum(outranks_old(a["hipporag"]["best_new"], a["hipporag"]["best_old"], 0) == "outranks" for _, a, _ in fired),
                    "outranks@0_fix": sum(outranks_old(b["hipporag"]["best_new"], b["hipporag"]["best_old"], 0) == "outranks" for _, _, b in fired),
                    "contamination_nofix": sum(a["hipporag"]["contamination_at5"] for _, a, _ in fired),
                    "contamination_fix": sum(b["hipporag"]["contamination_at5"] for _, _, b in fired),
                    "seed_o_nofix_gt0": sum((a["stage_c"]["seeds"].get("o") or 0) > 0 for _, a, _ in fired if a["stage_c"]),
                    "seed_o_fix_gt0": sum((b["stage_c"]["seeds"].get("o") or 0) > 0 for _, _, b in fired if b["stage_c"])}
            fx.append(e)
    out["fix"] = fx
    out["fix_fired_targets"] = sorted({t for (c, t), b in fix.items() if t in targets and b["fix_trace"]["dropped"]})

    # ---- where do the failures sit (attribution detail) ------------------------------------------------
    def best_rank(r, role):
        ranks = [p["rank"] for p in r["hipporag"]["passages"].values() if p["role"] == role]
        return min(ranks) if ranks else None
    fails = []
    for n in NS:
        for k in KS:
            rs = [nofix[((n, k), t)] for t in ids]
            bad = [r for r in rs if not r["hipporag"]["correction_at5"]]
            rk = [best_rank(r, "new") for r in bad]
            e = {"n": n, "k": k, "failures": len(bad),
                 "new_fact_not_candidate": sum(not r["flags"]["new_fact_in_candidates"] for r in bad),
                 "best_new_rank_6_10": sum(6 <= x <= 10 for x in rk), "best_new_rank_11_50": sum(11 <= x <= 50 for x in rk),
                 "best_new_rank_gt_50": sum(x > 50 for x in rk),
                 "with_old_passage_in_top5": sum(r["hipporag"]["contamination_at5"] > 0 for r in bad),
                 "new_outranks_old_but_outside_top5": sum(r["hipporag"]["best_new"] > r["hipporag"]["best_old"] for r in bad),
                 "old_outranks_new": sum(r["hipporag"]["best_new"] < r["hipporag"]["best_old"] for r in bad),
                 "dense_also_fails": sum(not r["dense"]["correction_at5"] for r in bad)}
            if n == 3:
                lost = [t for t in ids if nofix[((1, k), t)]["hipporag"]["correction_at5"] and not nofix[((3, k), t)]["hipporag"]["correction_at5"]]
                gained = [t for t in ids if not nofix[((1, k), t)]["hipporag"]["correction_at5"] and nofix[((3, k), t)]["hipporag"]["correction_at5"]]
                lr = [nofix[((3, k), t)] for t in lost]
                e["lost_vs_n1"] = {"targets": len(lost), "gained": len(gained),
                                   "old_passages_in_top5_mean": float(np.mean([r["hipporag"]["contamination_at5"] for r in lr])) if lr else None,
                                   "old_outranks_new": sum(r["hipporag"]["best_new"] < r["hipporag"]["best_old"] for r in lr),
                                   "best_new_rank_6_10": sum(6 <= best_rank(r, "new") <= 10 for r in lr),
                                   "new_fact_candidate": sum(r["flags"]["new_fact_in_candidates"] for r in lr)}
            fails.append(e)
    out["failures"] = fails

    # ---- long context --------------------------------------------------------------------------------
    lc = []
    for (n, k), rows in sorted(lc_rows.items()):
        rs = [r for r in rows if r["target_id"] in targets]
        c = collections.Counter(r["label"] for r in rs)
        e = {"n": n, "k": k, "N": len(rs), **{lab: c.get(lab, 0) for lab in ("o_prime", "o", "both", "neither")}}
        for lab, val in (("knows_yes", True), ("knows_no", False)):
            sub = [r for r in rs if knows[r["target_id"]] == val]
            e[f"o_prime_{lab}"] = rate(sum(r["label"] == "o_prime" for r in sub), len(sub))
        lc.append(e)
    out["long_context"] = lc
    return out


def pct(r):
    return "-" if r["rate"] is None else f"{r['num']}/{r['den']} ({r['rate']:.0%})"


def ci(b, scale=100, unit=""):
    return f"{b['mean'] * scale:+.1f}{unit} [{b['ci_lo'] * scale:+.1f}, {b['ci_hi'] * scale:+.1f}]"


def markdown(o, title):
    L = [f"# {title}", "", f"N = {o['N']} swaps (model_knows_o yes {o['model_knows_o']['yes']} / no {o['model_knows_o']['no']}). "
         "Source: `results/extension/grid_v5_20261109/*.jsonl` via `experiments/extension/phase_b.py`; full numbers in `phase_b.json`. "
         "CIs: 10,000 resamples of targets, seed 0, percentile 95 %.", "",
         "## Funnel (no-fix arm): is the fact among the top-5 candidates, and does the filter keep it", "",
         "| n | k | old candidate | new candidate | old kept | new kept | both kept | dense fallback | corr@5 if new is a candidate | corr@5 if not | dense corr@5 on those |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in o["funnel"]:
        extra = (f"{pct(e['correction_at5_if_new_candidate'])} | {pct(e['correction_at5_if_not_candidate'])} | {pct(e['dense_correction_at5_if_not_candidate'])}"
                 if e["k"] else "- | - | -")
        L.append(f"| {e['n']} | {e['k']} | {e['old_in_candidates']} | {e['new_in_candidates']} | {e['old_kept']} | {e['new_kept']} | "
                 f"{e['both_kept']} | {e['fallback_dense']} | {extra} |")
    L += ["", "## Filter keep rate for the correction", "",
          "| n | k | kept, given candidate | kept, of all questions | old kept, given candidate | given candidate, model knows o | given candidate, does not know o |",
          "|---|---|---|---|---|---|---|"]
    for e in o["filter"]:
        L.append(f"| {e['n']} | {e['k']} | {pct(e['new_kept_given_candidate'])} | {pct(e['new_kept_of_all_questions'])} | "
                 f"{pct(e['old_kept_given_candidate'])} | {pct(e['new_kept_given_candidate_knows_yes'])} | {pct(e['new_kept_given_candidate_knows_no'])} |")
    p = o["filter_pooled_given_candidate"]
    L += ["", "Pooled over the 8 k ≥ 1 cells, given the correction was a candidate: " +
          "; ".join(f"{lab} {pct(p[lab]['records'])} of records, per-target mean {p[lab]['mean_of_per_target_rates']['mean']:.0%} "
                    f"[{p[lab]['mean_of_per_target_rates']['ci_lo']:.0%}, {p[lab]['mean_of_per_target_rates']['ci_hi']:.0%}] over "
                    f"{p[lab]['targets_with_a_candidate_record']} targets" for lab in ("all", "knows_yes", "knows_no")) + "."]
    b = o["both_seeded"]
    L += ["", "## Records where the filter kept both the old and the new fact (k ≥ 1, no-fix)", "",
          f"{b['records']} records from {b['targets']} targets. correction@5 {pct(b['correction_at5'])}; o′ seeded {pct(b['seed_o_prime_gt_0'])}. "
          f"Median relative PPR margin |new − old| / max: {b['relative_ppr_margin_median']:.4f}. "
          f"Sign of the PPR margin equals the sign of the dense-cosine margin in {pct(b['ppr_margin_sign_equals_cosine_margin_sign'])} "
          f"(all k ≥ 1 records: {pct(b['all_records_sign_agreement'])}).", "", "| tolerance | outranks | near tie | loses |", "|---|---|---|---|"]
    for tol in TOLERANCES:
        x = b[f"outcome@{tol:g}"]
        L.append(f"| {tol:g} | {x['outranks']} | {x['near_tie']} | {x['loses']} |")
    L += ["", "## Effect of stale copies: correction@5 change from n = 1 to n = 3 (points)", "",
          "| k | HippoRAG 2 | dense | HippoRAG 2 − dense |", "|---|---|---|---|"]
    for e in o["n_effect"]["per_k"]:
        L.append(f"| {e['k']} | {ci(e['hipporag_change_n1_to_n3'])} | {ci(e['dense_change_n1_to_n3'])} | {ci(e['hipporag_minus_dense_change'])} |")
    e = o["n_effect"]["pooled_over_k"]
    L.append(f"| pooled | {ci(e['hipporag_change'])} | {ci(e['dense_change'])} | {ci(e['hipporag_minus_dense_change'])} |")
    L += ["", "## Pooled correction@5 (mean over cells per target, then over targets; %)", "",
          "| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense (points) | fix − HippoRAG 2 (points) |", "|---|---|---|---|---|---|"]
    f1 = lambda b: f"{b['mean'] * 100:.1f} [{b['ci_lo'] * 100:.1f}, {b['ci_hi'] * 100:.1f}]"
    for scope, e in o["pooled_correction_at5"].items():
        L.append(f"| {scope} | {f1(e['dense'])} | {f1(e['hipporag'])} | {f1(e['hipporag_fix'])} | {ci(e['hipporag_minus_dense'])} | {ci(e['fix_minus_hipporag'])} |")
    L += ["", "## Pooled contamination@5 (mean number of old passages in the top 5)", "",
          "| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense | fix − HippoRAG 2 |", "|---|---|---|---|---|---|"]
    f2 = lambda b: f"{b['mean']:.2f} [{b['ci_lo']:.2f}, {b['ci_hi']:.2f}]"
    f3 = lambda b: f"{b['mean']:+.2f} [{b['ci_lo']:+.2f}, {b['ci_hi']:+.2f}]"
    for scope, e in o["pooled_contamination_at5"].items():
        L.append(f"| {scope} | {f2(e['dense'])} | {f2(e['hipporag'])} | {f2(e['hipporag_fix'])} | {f3(e['hipporag_minus_dense'])} | {f3(e['fix_minus_hipporag'])} |")
    L += ["", "## Fix vs no fix", "", f"Targets where the fix ever fired: {len(o['fix_fired_targets'])}.", "",
          "| n | k | fix fired | top 5 identical | corr@5 no fix → fix | where fired: corr@5 | where fired: outranks@0 | where fired: old passages in top 5 | where fired: o seeded | other-gold recall@5 no fix → fix (records changed) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for e in o["fix"]:
        if e["k"]:
            w = e["where_fired"]
            mid = (f"{e['correction_at5_nofix']:.3f} → {e['correction_at5_fix']:.3f} | {w['correction_at5_nofix']} → {w['correction_at5_fix']} | "
                   f"{w['outranks@0_nofix']} → {w['outranks@0_fix']} | {w['contamination_nofix']} → {w['contamination_fix']} | {w['seed_o_nofix_gt0']} → {w['seed_o_fix_gt0']}")
        else:
            mid = "- | - | - | - | -"
        L.append(f"| {e['n']} | {e['k']} | {e['fix_fired_records']} | {e['top5_identical_records']}/{o['N']} | {mid} | "
                 f"{e['other_gold_recall_at5_nofix']:.3f} → {e['other_gold_recall_at5_fix']:.3f} ({e['other_gold_recall_changed_records']}) |")
    L += ["", "## HippoRAG 2 correction@5 failures (no-fix arm): where the correction sits", "",
          "| n | k | failures | new fact not a candidate | best correction at rank 6–10 | 11–50 | > 50 | an old passage in top 5 | old outranks new | new outranks old, still outside | dense also fails | lost vs n = 1 (gained) | of the lost: old outranks new / rank 6–10 / mean old in top 5 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in o["failures"]:
        lv = e.get("lost_vs_n1")
        tail = (f"{lv['targets']} ({lv['gained']}) | {lv['old_outranks_new']} / {lv['best_new_rank_6_10']} / {lv['old_passages_in_top5_mean']:.2f}"
                if lv and lv["targets"] else "- | -")
        L.append(f"| {e['n']} | {e['k']} | {e['failures']} | {e['new_fact_not_candidate']} | {e['best_new_rank_6_10']} | {e['best_new_rank_11_50']} | "
                 f"{e['best_new_rank_gt_50']} | {e['with_old_passage_in_top5']} | {e['old_outranks_new']} | {e['new_outranks_old_but_outside_top5']} | "
                 f"{e['dense_also_fails']} | {tail} |")
    L += ["", "## Long-context reader (all of the question's passages plus every injected variant)", "",
          "| n | k | N | answers o′ | answers o | both | neither | o′ when model knows o | o′ when it does not |", "|---|---|---|---|---|---|---|---|---|"]
    for e in o["long_context"]:
        L.append(f"| {e['n']} | {e['k']} | {e['N']} | {e['o_prime']} | {e['o']} | {e['both']} | {e['neither']} | {pct(e['o_prime_knows_yes'])} | {pct(e['o_prime_knows_no'])} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(RESULTS))
    ap.add_argument("--targets", default=str(DATA_DIR / "targets_v5.jsonl"))
    ap.add_argument("--final", default=str(DATA_DIR / "targets_final.jsonl"))
    ap.add_argument("--review", default=str(DATA_DIR / "review_v5.md"))
    ap.add_argument("--drop_rows", default="", help="comma-separated review row numbers to exclude (sensitivity)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    targets = {json.loads(l)["target_id"]: json.loads(l) for l in Path(a.targets).read_text(encoding="utf-8").splitlines() if l.strip()}
    targets, records = restrict_to_final(targets, load_records(a.results), a.final)
    title = "Phase B numbers: final targets"
    if a.drop_rows:
        rows = row_ids(a.review)
        drop = {rows[int(x)] for x in a.drop_rows.split(",")}
        missing = drop - set(targets)
        if missing:
            raise SystemExit(f"rows not in the final set: {sorted(missing)}")
        targets = {t: v for t, v in targets.items() if t not in drop}
        records = [r for r in records if r["target_id"] in targets]
        title += f" minus review rows {a.drop_rows}"
    lc = {}
    for p in sorted(Path(a.results).glob("long_context_n*_k*.jsonl")):
        n, k = map(int, re.match(r"long_context_n(\d+)_k(\d+)", p.name).groups())
        lc[(n, k)] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    samples = {s["id"]: s for s in json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))}
    o = compute(targets, records, lc, samples)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "phase_b.json").write_text(json.dumps(o, indent=1), encoding="utf-8")
    (out / "phase_b.md").write_text(markdown(o, title), encoding="utf-8")
    (out / "targets_used.txt").write_text("\n".join(sorted(targets)) + "\n", encoding="utf-8")
    print(f"N = {o['N']}; wrote {out}/phase_b.json, phase_b.md, targets_used.txt")


if __name__ == "__main__":
    main()
