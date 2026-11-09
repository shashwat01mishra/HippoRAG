"""Analysis of a grid run (offline). Reads <results>/cell_n*_k*.jsonl and the targets file.

Arms: dense (dense retrieval on the cell's index, from the no-fix records), hipporag, hipporag_fix.
Unit of analysis: one target = one distinct gold passage = one swap (N counts distinct swaps).
Metrics by (n, k) and slice. Slices: 'all', plus frequency bins (FREQ_SPLITS: corpus passage frequency of o and
of o', 0 if absent) for a split only when every bin of that split has >= MIN_BIN swaps:
  correction@5 (k >= 1), contamination@5 (mean number of old passages in the top 5),
  outranks / near_tie / loses at each tolerance in TOLERANCES, computed here from the raw best_new / best_old
  scores logged per record (PPR scores for the HippoRAG arms, raw cosine for dense).
Attribution (HippoRAG arms, k >= 1, correction@5 failures only): the first failing stage under STAGE_ORDER,
with predicates in STAGE_RULES (both configurable):
  A  the new fact (s, r, o') is not among the top-5 candidate facts
  B  the filter did not keep it (for the fix arm: not kept after the fix)
  C  o' is not a seeded phrase (zero reset probability; includes the dense fallback)
  D  the PPR margin favours the old passage beyond the tolerance (outcome 'loses')
  E_tie    near tie with the old passage (within the tolerance), outside the top 5
  E_crowd  outranks the old passage beyond the tolerance, still outside the top 5 (crowded out by other passages)
Successes are labelled 'ok'. Dense-arm failures are not attributed (the stages do not exist there).

    .venv/bin/python experiments/extension/analysis.py --results <root>/results --out <dir>
    .venv/bin/python experiments/extension/analysis.py --results <root>/results --trace --cell 1,1 --n_trace 3
"""
import argparse
import collections
import json
import random
import sys

import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.attrib_rag import outranks_old  # noqa: E402
from experiments.extension.common import TARGETS_PATH, text_processing as tp  # noqa: E402

TOLERANCES = (0.0, 0.005, 0.01, 0.02)
ARMS = ("dense", "hipporag", "hipporag_fix")
OUTCOMES = ("outranks", "near_tie", "loses")
STAGE_ORDER = ("A", "B", "C", "D", "E_tie", "E_crowd")


def _new_fact(t):
    return [tp(t["s"]), tp(t["r"]), tp(t["o_prime"])]


STAGE_RULES = {
    "A": lambda rec, arm, t, tol: not rec["flags"]["new_fact_in_candidates"],
    "B": lambda rec, arm, t, tol: _new_fact(t) not in (rec["fix_trace"]["kept"] if arm == "hipporag_fix" else rec["stage_b"]["kept"]),
    "C": lambda rec, arm, t, tol: rec["stage_c"] is None or not (rec["stage_c"]["seeds"].get("o_prime") or 0) > 0,
    "D": lambda rec, arm, t, tol: outranks_old(rec["hipporag"]["best_new"], rec["hipporag"]["best_old"], tol) == "loses",
    "E_tie": lambda rec, arm, t, tol: outranks_old(rec["hipporag"]["best_new"], rec["hipporag"]["best_old"], tol) == "near_tie",
    "E_crowd": lambda rec, arm, t, tol: outranks_old(rec["hipporag"]["best_new"], rec["hipporag"]["best_old"], tol) == "outranks",
}


def first_failure(rec, arm, target, tol, order=STAGE_ORDER, rules=None):
    """None for k=0, 'ok' when the correction is in the top 5, else the first stage whose predicate holds."""
    rules = rules or STAGE_RULES
    r = rec["hipporag"]
    if r["correction_at5"] is None:
        return None
    if r["correction_at5"]:
        return "ok"
    for stage in order:
        if rules[stage](rec, arm, target, tol):
            return stage
    return "unattributed"


MIN_BIN = 15
FREQ_SPLITS = {   # name: (target field, [(lo, hi or None, label)])  frequency = passages whose triples contain the entity
    "o_prime_freq": ("freq_oprime_graph", [(0, 0, "absent"), (1, 9, "1-9"), (10, None, ">=10")]),
    "o_freq": ("freq_o_graph", [(1, 1, "1"), (2, 9, "2-9"), (10, None, ">=10")]),
    # closed-book probe (targets v5): does the model know o for (s, r, ?) without context
    "model_knows_o": ("model_knows_o", [(1, 1, "yes"), (0, 0, "no")]),
}


def slice_map(targets_by_id, min_bin=MIN_BIN, splits=None):
    """({target_id: [slice labels]}, {split: {bin: count, 'used': bool}}). A split is used only if every bin
    has >= min_bin targets (distinct swaps); 'all' is always present."""
    splits = FREQ_SPLITS if splits is None else splits
    labels = {tid: ["all"] for tid in targets_by_id}
    report = {}
    for name, (field, bins) in splits.items():
        assign = {}
        for tid, t in targets_by_id.items():
            f = int(t.get(field) or 0)
            assign[tid] = next((lab for lo, hi, lab in bins if f >= lo and (hi is None or f <= hi)), None)
        counts = collections.Counter(assign.values())
        used = all(counts.get(lab, 0) >= min_bin for _, _, lab in bins)
        report[name] = {**{lab: counts.get(lab, 0) for _, _, lab in bins}, "used": used}
        if used:
            for tid, lab in assign.items():
                if lab is not None:
                    labels[tid].append(f"{name}:{lab}")
    return labels, report


def restrict_to_final(targets_by_id, records, final_path):
    """Keep only targets listed in targets_final.jsonl (and their records). Every final id must exist."""
    final_ids = {json.loads(l)["target_id"] for l in Path(final_path).read_text(encoding="utf-8").splitlines() if l.strip()}
    unknown = final_ids - set(targets_by_id)
    if unknown:
        raise ValueError(f"{len(unknown)} id(s) in {final_path} are not in the targets file, e.g. {sorted(unknown)[:3]}")
    return ({tid: t for tid, t in targets_by_id.items() if tid in final_ids},
            [r for r in records if r["target_id"] in final_ids])


def load_records(results_dir):
    records = []
    for path in sorted(Path(results_dir).glob("cell_n*_k*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return records


def flatten(records, targets_by_id, tolerances=TOLERANCES, min_bin=MIN_BIN):
    """One row per (record, arm): the dense arm is taken from no-fix records only."""
    slices, _ = slice_map(targets_by_id, min_bin)
    rows = []
    for rec in records:
        t = targets_by_id[rec["target_id"]]
        n, k = rec["cell"]
        arms = [("hipporag_fix", rec["hipporag"])] if rec["fix"] else [("hipporag", rec["hipporag"]), ("dense", rec["dense"])]
        for arm, r in arms:
            row = {"arm": arm, "n": n, "k": k, "slices": slices[rec["target_id"]], "target_id": rec["target_id"],
                   "freq_o": t.get("freq_o_graph"), "freq_oprime": t.get("freq_oprime_graph"),
                   "group": rec.get("group", 0),
                   "correction_at5": r["correction_at5"], "contamination_at5": r["contamination_at5"],
                   "best_new": r["best_new"], "best_old": r["best_old"], "rehearsal": rec.get("rehearsal", False)}
            if arm == "hipporag_fix":
                old_fact = [tp(t["s"]), tp(t["r"]), tp(t["o"])]
                dropped = [d["fact"] for d in rec["fix_trace"]["dropped"]]
                row["fix_dropped_target_old"] = sum(f == old_fact for f in dropped)
                row["fix_dropped_other"] = sum(f != old_fact for f in dropped)     # false-positive path
            for tol in tolerances:
                row[f"outcome@{tol}"] = outranks_old(r["best_new"], r["best_old"], tol)
                row[f"stage@{tol}"] = first_failure(rec, arm, t, tol) if arm != "dense" else None
            rows.append(row)
    return rows


def summarize(rows, tolerances=TOLERANCES):
    """Metric table keyed by (arm, n, k, slice); N = distinct swaps in the slice."""
    groups = collections.defaultdict(list)
    for row in rows:
        for sl in row["slices"]:
            groups[(row["arm"], row["n"], row["k"], sl)].append(row)
    table = []
    for (arm, n, k, sl), rs in sorted(groups.items()):
        entry = {"arm": arm, "n": n, "k": k, "slice": sl, "N": len(rs),
                 "contamination_at5": sum(r["contamination_at5"] for r in rs) / len(rs)}
        corr = [r["correction_at5"] for r in rs if r["correction_at5"] is not None]
        entry["correction_at5"] = sum(corr) / len(corr) if corr else None
        entry["fix_collateral_drops"] = sum(r.get("fix_dropped_other", 0) for r in rs) if arm == "hipporag_fix" else None
        for tol in tolerances:
            outs = [r[f"outcome@{tol}"] for r in rs if r[f"outcome@{tol}"] is not None]
            for o in OUTCOMES:
                entry[f"{o}@{tol}"] = outs.count(o) / len(outs) if outs else None
        table.append(entry)
    return table


def attribution_counts(rows, tolerances=TOLERANCES):
    out = []
    groups = collections.defaultdict(list)
    for row in rows:
        if row["arm"] != "dense" and row["k"] > 0:
            for sl in row["slices"]:
                groups[(row["arm"], row["n"], row["k"], sl)].append(row)
    for (arm, n, k, sl), rs in sorted(groups.items()):
        for tol in tolerances:
            c = collections.Counter(r[f"stage@{tol}"] for r in rs)
            out.append({"arm": arm, "n": n, "k": k, "slice": sl, "tol": tol, "N": len(rs),
                        **{s: c.get(s, 0) for s in ("ok", *STAGE_ORDER, "unattributed")}})
    return out


# ------------------------------------------------------------------ paired bootstrap ------------------
COMPARISONS = (("hipporag", "dense"), ("hipporag_fix", "hipporag"))   # (arm a, arm b): report a - b
BOOT_METRICS = ("correction_at5", "contamination_at5")


def paired_bootstrap(rows, metric, arm_a, arm_b, n_boot=10000, seed=0, alpha=0.05):
    """Per (n, k): mean of (a - b) over targets present in both arms, with a percentile CI from resampling targets
    (pairs kept together). Cells where the metric is undefined (correction@5 at k = 0) are skipped."""
    by = collections.defaultdict(dict)
    for r in rows:
        if r["arm"] in (arm_a, arm_b) and r[metric] is not None:
            by[(r["n"], r["k"], r["arm"])][r["target_id"]] = float(r[metric])
    out = []
    for n, k in sorted({(r["n"], r["k"]) for r in rows}):
        a, b = by.get((n, k, arm_a), {}), by.get((n, k, arm_b), {})
        ids = sorted(set(a) & set(b))
        if not ids:
            continue
        diffs = np.array([a[t] - b[t] for t in ids])
        rng = np.random.default_rng(seed)
        boots = diffs[rng.integers(0, len(ids), size=(n_boot, len(ids)))].mean(axis=1)
        lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        out.append({"metric": metric, "a": arm_a, "b": arm_b, "n": n, "k": k, "N": len(ids),
                    "mean_a": float(np.mean([a[t] for t in ids])), "mean_b": float(np.mean([b[t] for t in ids])),
                    "diff": float(diffs.mean()), "ci_lo": float(lo), "ci_hi": float(hi), "n_boot": n_boot, "seed": seed})
    return out


def bootstrap_all(rows, n_boot=10000, seed=0):
    return [e for metric in BOOT_METRICS for a, b in COMPARISONS for e in paired_bootstrap(rows, metric, a, b, n_boot, seed)]


# ------------------------------------------------------------------ LaTeX export ----------------------
TEX_ARM = {"dense": "Dense", "hipporag": "HippoRAG\\,2", "hipporag_fix": "+\\,fix"}


def _f(v, digits=2):
    return "--" if v is None else f"{v:.{digits}f}"


def latex_tables(table, boot, attrib, rows, tol=0.01):
    """{filename: LaTeX tabular} for the paper's \\input stubs (booktabs; slice 'all')."""
    cells = sorted({(e["n"], e["k"]) for e in table})
    look = {(e["arm"], e["n"], e["k"]): e for e in table if e["slice"] == "all"}
    out = {}

    lines = ["\\begin{tabular}{rr ccc ccc}", "\\toprule",
             " & & \\multicolumn{3}{c}{correction@5} & \\multicolumn{3}{c}{contamination@5} \\\\",
             "\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}",
             "$n$ & $k$ & " + " & ".join(TEX_ARM[a] for a in ARMS) + " & " + " & ".join(TEX_ARM[a] for a in ARMS) + " \\\\",
             "\\midrule"]
    for n, k in cells:
        corr = [_f(look.get((a, n, k), {}).get("correction_at5")) for a in ARMS]
        cont = [_f(look.get((a, n, k), {}).get("contamination_at5")) for a in ARMS]
        lines.append(f"{n} & {k} & " + " & ".join(corr) + " & " + " & ".join(cont) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    out["tab_main.tex"] = "\n".join(lines) + "\n"

    def ci(e):
        return f"{e['diff']:+.2f} [{e['ci_lo']:+.2f}, {e['ci_hi']:+.2f}]"
    bl = {(e["metric"], e["a"], e["b"], e["n"], e["k"]): e for e in boot}
    lines = ["\\begin{tabular}{rr cc}", "\\toprule",
             "$n$ & $k$ & HippoRAG\\,2 $-$ dense & fix $-$ no fix \\\\", "\\midrule"]
    for n, k in cells:
        if k == 0:
            continue
        pair = [bl.get(("correction_at5", a, b, n, k)) for a, b in COMPARISONS]
        lines.append(f"{n} & {k} & " + " & ".join(ci(e) if e else "--" for e in pair) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    out["tab_bootstrap.tex"] = "\n".join(lines) + "\n"

    stages = ("ok", *STAGE_ORDER)
    head = {"ok": "ok", "A": "A", "B": "B", "C": "C", "D": "D", "E_tie": "E$_\\text{tie}$", "E_crowd": "E$_\\text{crowd}$"}
    lines = ["\\begin{tabular}{lrr " + "r" * len(stages) + "}", "\\toprule",
             "Arm & $n$ & $k$ & " + " & ".join(head[s] for s in stages) + " \\\\", "\\midrule"]
    for e in attrib:
        if e["slice"] == "all" and e["tol"] == tol:
            lines.append(f"{TEX_ARM[e['arm']]} & {e['n']} & {e['k']} & " + " & ".join(str(e[s]) for s in stages) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    out["tab_attribution.tex"] = "\n".join(lines) + "\n"

    lines = ["\\begin{tabular}{l " + "c" * len(TOLERANCES) + "}", "\\toprule",
             "Arm & " + " & ".join(f"$\\tau={100 * t:g}\\%$" for t in TOLERANCES) + " \\\\", "\\midrule"]
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm and r["k"] > 0]
        cellv = []
        for t in TOLERANCES:
            outs = [r[f"outcome@{t}"] for r in rs if r[f"outcome@{t}"] is not None]
            cellv.append("/".join(_f(outs.count(o) / len(outs)) if outs else "--" for o in OUTCOMES))
        lines.append(f"{TEX_ARM[arm]} & " + " & ".join(cellv) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    out["tab_tolerance.tex"] = "\n".join(lines) + "\n"
    return out


def write_csv(path, table):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)


# ------------------------------------------------------------------ figures -----------------------
# Reference palette (dataviz skill, references/palette.md): categorical slots 1-3 are validated all-pairs,
# slots 1-5 adjacent; outcomes use the documented blue <-> red diverging pair with a gray midpoint.
ARM_COLOR = {"dense": "#2a78d6", "hipporag": "#eb6834", "hipporag_fix": "#1baf7a"}
ARM_LABEL = {"dense": "Dense", "hipporag": "HippoRAG 2", "hipporag_fix": "HippoRAG 2 + fix"}
ARM_MARKER = {"dense": "o", "hipporag": "s", "hipporag_fix": "^"}
OUTCOME_COLOR = {"outranks": "#2a78d6", "near_tie": "#c3c2b7", "loses": "#e34948"}
STAGE_COLOR = {"ok": "#c3c2b7", "A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100", "E_tie": "#e87ba4",
               "E_crowd": "#008300",
               "unattributed": "#52514e"}
INK, INK2, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _lookup(table, arm, n, k, sl, key):
    for e in table:
        if (e["arm"], e["n"], e["k"], e["slice"]) == (arm, n, k, sl):
            return e[key]
    return None


def plot_slices(table):
    """Figure columns: 'all', the model_knows_o bins, then the o' frequency bins, for splits in use
    (o frequency bins stay in the tables)."""
    present = {e["slice"] for e in table}
    order = (["all"] + [f"model_knows_o:{lab}" for _, _, lab in FREQ_SPLITS["model_knows_o"][1]]
             + [f"o_prime_freq:{lab}" for _, _, lab in FREQ_SPLITS["o_prime_freq"][1]])
    return [s for s in order if s in present]


def _slice_title(sl):
    if sl == "all":
        return "all swaps"
    name, lab = sl.split(":", 1)
    return f"model knows o: {lab}" if name == "model_knows_o" else f"o′ frequency {lab}"


def plot_lines(table, key, title, ylabel, path, ks, ylim=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ns = sorted({e["n"] for e in table})
    cols = plot_slices(table)
    fig, axes = plt.subplots(len(ns), len(cols), figsize=(4.5 * len(cols), 3.2 * len(ns)), sharex=True, sharey=True,
                             squeeze=False, facecolor=SURFACE)
    for i, n in enumerate(ns):
        for j, sl in enumerate(cols):
            ax = axes[i][j]
            _style(ax)
            for arm in ARMS:
                pts = [(k, _lookup(table, arm, n, k, sl, key)) for k in ks]
                pts = [(k, v) for k, v in pts if v is not None]
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=ARM_COLOR[arm], linewidth=2,
                            marker=ARM_MARKER[arm], markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5,
                            label=ARM_LABEL[arm])
            n_swaps = _lookup(table, "hipporag", n, ks[-1], sl, "N")
            ax.set_title(f"n = {n} old copies, {_slice_title(sl)} (N = {n_swaps})", fontsize=9, color=INK, loc="left")
            ax.set_xticks(ks)
            if ylim:
                ax.set_ylim(*ylim)
            else:                                   # counts: floor at 0, never an empty negative range
                top = max([v for e in table if e["k"] in ks for v in [e[key]] if v is not None] + [0.0])
                ax.set_ylim(0, max(1.0, top * 1.1))
            if i == len(ns) - 1:
                ax.set_xlabel("k corrections", fontsize=8, color=INK2)
            if j == 0:
                ax.set_ylabel(ylabel, fontsize=8, color=INK2)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_stacks(rows, field, categories, colors, labels, title, path, arms, tol):
    """Stacked shares per cell (k >= 1), one panel per arm."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cells = sorted({(r["n"], r["k"]) for r in rows if r["k"] > 0})
    fig, axes = plt.subplots(1, len(arms), figsize=(4.2 * len(arms), 3.6), sharey=True, squeeze=False, facecolor=SURFACE)
    for ax, arm in zip(axes[0], arms):
        _style(ax)
        x = range(len(cells))
        bottom = [0.0] * len(cells)
        for cat in categories:
            vals = []
            for n, k in cells:
                rs = [r[field] for r in rows if r["arm"] == arm and (r["n"], r["k"]) == (n, k) and r[field] is not None]
                vals.append(rs.count(cat) / len(rs) if rs else 0.0)
            ax.bar(x, vals, bottom=bottom, width=0.72, color=colors[cat], edgecolor=SURFACE, linewidth=1.0, label=labels[cat])
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"{n},{k}" for n, k in cells], fontsize=7)
        ax.set_xlabel("cell (n, k)", fontsize=8, color=INK2)
        ax.set_title(ARM_LABEL[arm], fontsize=9, color=INK, loc="left")
        ax.set_ylim(0, 1)
    axes[0][0].set_ylabel("share of questions", fontsize=8, color=INK2)
    handles, lbls = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, lbls, loc="upper right", ncol=len(categories), frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle(f"{title} (tolerance {tol:g})", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# ------------------------------------------------------------------ trace printer -----------------
def print_trace(rec, target):
    def fact(f):
        return f"({' | '.join(f)})"
    print(f"\n=== {rec['target_id']}  cell {rec['cell']}  fix={rec['fix']}  "
          f"[freq o={target.get('freq_o_graph')}, o'={target.get('freq_oprime_graph')}]")
    print(f"Q: {rec['question']}")
    print(f"swap: ({target['s']} | {target['r']} | {target['o']} -> {target['o_prime']})")
    print("A  candidates:")
    for f in rec["stage_a"]:
        print(f"     {f['score']:.4f}  {fact(f['fact'])}")
    print(f"B  kept by filter: {[fact(f) for f in rec['stage_b']['kept']]}  fallback_dense={rec['fallback_dense']}")
    if rec.get("fix_trace"):
        print(f"   fix dropped: {rec['fix_trace']['dropped']}")
    print(f"   flags: {rec['flags']}")
    if rec["stage_c"]:
        c = rec["stage_c"]
        print(f"C  reset: total {c['reset_total']:.4g}, phrase mass {c['phrase_mass']:.4g}, passage mass "
              f"{c['passage_mass']:.4g}, phrase seeds {c['n_phrase_seeds']}")
        for key in ("s", "o", "o_prime"):
            print(f"     seed[{key}] = {c['seeds'].get(key)}")
    else:
        print("C  (dense fallback: no PPR)")
    for arm in ("hipporag", "dense"):
        r = rec[arm]
        num = lambda v: "-" if v is None else f"{v:.6g}"
        print(f"D  [{arm}] best_old {num(r['best_old'])}  best_new {num(r['best_new'])}  "
              f"margin(old-new) {num(r['margin_old_minus_new'])}")
        for cid, p in r["passages"].items():
            print(f"     {p['role']:4s} rank {p['rank']:6d}  score {p['score']:.6g}  cosine {p['cosine']:.4f}  {cid[:14]}")
        print(f"E  [{arm}] top5 roles {[x['role'] for x in r['top5']]}  correction@5={r['correction_at5']}  "
              f"contamination@5={r['contamination_at5']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", required=True)
    parser.add_argument("--targets", default=str(TARGETS_PATH))
    parser.add_argument("--out", help="directory for CSV/markdown tables and PNG figures")
    parser.add_argument("--plot_tol", type=float, default=0.01, help="tolerance used in the stacked figures")
    parser.add_argument("--trace", action="store_true", help="print full stage A-E traces")
    parser.add_argument("--cell", default="1,1")
    parser.add_argument("--n_trace", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--final", help="targets_final.jsonl: analyse only these targets (hand-reviewed keep = y)")
    parser.add_argument("--tex_dir", help="also write LaTeX tables here (the paper inputs paper/tables/*.tex)")
    parser.add_argument("--n_boot", type=int, default=10000)
    args = parser.parse_args()

    targets = {json.loads(l)["target_id"]: json.loads(l) for l in Path(args.targets).read_text(encoding="utf-8").splitlines() if l.strip()}
    records = load_records(args.results)
    if args.final:
        targets, records = restrict_to_final(targets, records, args.final)
        print(f"restricted to {len(targets)} targets from {args.final} ({len(records)} records)")
    if args.trace:
        cell = list(map(int, args.cell.split(",")))
        recs = [r for r in records if r["cell"] == cell and not r["fix"]]
        for rec in random.Random(args.seed).sample(recs, min(args.n_trace, len(recs))):
            print_trace(rec, targets[rec["target_id"]])
        return
    rows = flatten(records, targets)
    if any(r["rehearsal"] for r in rows):
        print("NOTE: rehearsal records (random vectors, fake filter): numbers are meaningless, format only.")
    table = summarize(rows)
    attrib = attribution_counts(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "metrics.csv", table)
    write_csv(out / "attribution.csv", attrib)
    boot = bootstrap_all(rows, n_boot=args.n_boot, seed=args.seed)
    write_csv(out / "bootstrap.csv", boot)
    tex_dir = Path(args.tex_dir) if args.tex_dir else out / "tex"
    tex_dir.mkdir(parents=True, exist_ok=True)
    for name, body in latex_tables(table, boot, attrib, rows, tol=args.plot_tol).items():
        (tex_dir / name).write_text(body, encoding="utf-8")
    print(f"wrote bootstrap.csv and LaTeX tables to {tex_dir}")
    ks_all = sorted({r["k"] for r in rows})
    plot_lines(table, "correction_at5", "Correction in top 5", "correction@5", out / "correction_at5.png",
               [k for k in ks_all if k > 0], ylim=(-0.03, 1.03))
    plot_lines(table, "contamination_at5", "Old passages in top 5", "contamination@5 (mean count)",
               out / "contamination_at5.png", ks_all)
    plot_stacks(rows, f"outcome@{args.plot_tol}", OUTCOMES, OUTCOME_COLOR,
                {"outranks": "outranks", "near_tie": "near tie", "loses": "loses"},
                "Best correction vs best old passage", out / "outranks_old.png", ARMS, args.plot_tol)
    plot_stacks(rows, f"stage@{args.plot_tol}", ("ok", *STAGE_ORDER), STAGE_COLOR,
                {"ok": "ok (in top 5)", "A": "A not a candidate", "B": "B filtered out", "C": "C o′ not seeded",
                 "D": "D margin favours old", "E_tie": "E tie, outside top 5", "E_crowd": "E outranks, crowded out"},
                "First failure stage", out / "attribution.png", ("hipporag", "hipporag_fix"), args.plot_tol)

    _, split_report = slice_map(targets, MIN_BIN)
    n_swaps = len({r["target_id"] for r in rows})
    lines = [f"N = {n_swaps} distinct swaps (one question per gold passage).", "",
             f"Frequency splits (used only if every bin has >= {MIN_BIN} swaps): " +
             "; ".join(f"{name} {rep}" for name, rep in split_report.items()), ""]
    lines += ["| arm | n | k | slice | N | correction@5 | contamination@5 | " +
              " | ".join(f"out/tie/lose @{t:g}" for t in TOLERANCES) + " |", "|" + "---|" * (7 + len(TOLERANCES))]
    fmt = lambda v: "-" if v is None else f"{v:.2f}"
    for e in table:
        lines.append(f"| {e['arm']} | {e['n']} | {e['k']} | {e['slice']} | {e['N']} | {fmt(e['correction_at5'])} | "
                     f"{e['contamination_at5']:.2f} | " +
                     " | ".join("/".join(fmt(e[f'{o}@{t}']) for o in OUTCOMES) for t in TOLERANCES) + " |")
    lines += ["", "| arm | n | k | slice | tol | N | ok | A | B | C | D | E_tie | E_crowd |", "|" + "---|" * 13]
    for a in attrib:
        lines.append(f"| {a['arm']} | {a['n']} | {a['k']} | {a['slice']} | {a['tol']:g} | {a['N']} | {a['ok']} | "
                     f"{a['A']} | {a['B']} | {a['C']} | {a['D']} | {a['E_tie']} | {a['E_crowd']} |")
    fix_rows = [r for r in rows if r["arm"] == "hipporag_fix"]
    lines += ["", "Fix collateral drops (non-target facts dropped by the fix; the false-positive path of oracle detection)",
              "", "| fix drops | n | k | records | dropped target old fact | dropped other facts (collateral) |", "|---|---|---|---|---|---|"]
    for n, k in sorted({(r["n"], r["k"]) for r in fix_rows}):
        rs = [r for r in fix_rows if (r["n"], r["k"]) == (n, k)]
        lines.append(f"| | {n} | {k} | {len(rs)} | {sum(r['fix_dropped_target_old'] for r in rs)} | "
                     f"{sum(r['fix_dropped_other'] for r in rs)} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote metrics.csv, attribution.csv, summary.md and 4 PNGs to {out}")


if __name__ == "__main__":
    main()
