"""Analysis of a grid run (offline). Reads <results>/cell_n*_k*.jsonl and the targets file.

Arms: dense (dense retrieval on the cell's index, from the no-fix records), hipporag, hipporag_fix.
Metrics by (n, k) and stratum (rare / common / all):
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


def load_records(results_dir):
    records = []
    for path in sorted(Path(results_dir).glob("cell_n*_k*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return records


def flatten(records, targets_by_id, tolerances=TOLERANCES):
    """One row per (record, arm): the dense arm is taken from no-fix records only."""
    rows = []
    for rec in records:
        t = targets_by_id[rec["target_id"]]
        n, k = rec["cell"]
        arms = [("hipporag_fix", rec["hipporag"])] if rec["fix"] else [("hipporag", rec["hipporag"]), ("dense", rec["dense"])]
        for arm, r in arms:
            row = {"arm": arm, "n": n, "k": k, "stratum": t["stratum"], "target_id": rec["target_id"],
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
    """Metric table keyed by (arm, n, k, stratum) with stratum 'all' added."""
    groups = collections.defaultdict(list)
    for row in rows:
        for stratum in (row["stratum"], "all"):
            groups[(row["arm"], row["n"], row["k"], stratum)].append(row)
    table = []
    for (arm, n, k, stratum), rs in sorted(groups.items()):
        entry = {"arm": arm, "n": n, "k": k, "stratum": stratum, "N": len(rs),
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
            for stratum in (row["stratum"], "all"):
                groups[(row["arm"], row["n"], row["k"], stratum)].append(row)
    for (arm, n, k, stratum), rs in sorted(groups.items()):
        for tol in tolerances:
            c = collections.Counter(r[f"stage@{tol}"] for r in rs)
            out.append({"arm": arm, "n": n, "k": k, "stratum": stratum, "tol": tol, "N": len(rs),
                        **{s: c.get(s, 0) for s in ("ok", *STAGE_ORDER, "unattributed")}})
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


def _lookup(table, arm, n, k, stratum, key):
    for e in table:
        if (e["arm"], e["n"], e["k"], e["stratum"]) == (arm, n, k, stratum):
            return e[key]
    return None


def plot_lines(table, key, title, ylabel, path, ks, ylim=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ns = sorted({e["n"] for e in table})
    fig, axes = plt.subplots(len(ns), 2, figsize=(9, 3.2 * len(ns)), sharex=True, sharey=True, squeeze=False,
                             facecolor=SURFACE)
    for i, n in enumerate(ns):
        for j, stratum in enumerate(("rare", "common")):
            ax = axes[i][j]
            _style(ax)
            for arm in ARMS:
                pts = [(k, _lookup(table, arm, n, k, stratum, key)) for k in ks]
                pts = [(k, v) for k, v in pts if v is not None]
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=ARM_COLOR[arm], linewidth=2,
                            marker=ARM_MARKER[arm], markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5,
                            label=ARM_LABEL[arm])
            ax.set_title(f"n = {n} old copies, {stratum} o′", fontsize=9, color=INK, loc="left")
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
    print(f"\n=== {rec['target_id']}  cell {rec['cell']}  fix={rec['fix']}  [{target['stratum']}]")
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
    args = parser.parse_args()

    targets = {json.loads(l)["target_id"]: json.loads(l) for l in Path(args.targets).read_text(encoding="utf-8").splitlines() if l.strip()}
    records = load_records(args.results)
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

    lines = ["| arm | n | k | stratum | N | correction@5 | contamination@5 | " +
             " | ".join(f"out/tie/lose @{t:g}" for t in TOLERANCES) + " |", "|" + "---|" * (7 + len(TOLERANCES))]
    fmt = lambda v: "-" if v is None else f"{v:.2f}"
    for e in table:
        lines.append(f"| {e['arm']} | {e['n']} | {e['k']} | {e['stratum']} | {e['N']} | {fmt(e['correction_at5'])} | "
                     f"{e['contamination_at5']:.2f} | " +
                     " | ".join("/".join(fmt(e[f'{o}@{t}']) for o in OUTCOMES) for t in TOLERANCES) + " |")
    lines += ["", "| arm | n | k | stratum | tol | N | ok | A | B | C | D | E_tie | E_crowd |", "|" + "---|" * 13]
    for a in attrib:
        lines.append(f"| {a['arm']} | {a['n']} | {a['k']} | {a['stratum']} | {a['tol']:g} | {a['N']} | {a['ok']} | "
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
