"""Deck figures (PDF) from the analysis outputs. Nothing is typed in by hand: every plotted value is read from
analysis/grid_v5_final/{metrics.csv,bootstrap.csv,phase_b.json}.

    .venv/bin/python deck/make_figs.py
"""
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "analysis" / "grid_v5_final"
OUT = Path(__file__).resolve().parent / "figs"
ACCENT, GRAY, INK, INK2, GRID = "#2a78d6", "#8a8984", "#0b0b0b", "#52514e", "#e1e0d9"
plt.rcParams.update({"font.family": "Helvetica", "font.size": 13, "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "pdf.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#c3c2b7"})


def metrics():
    return {(r["arm"], int(r["n"]), int(r["k"])): r for r in csv.DictReader(open(A / "metrics.csv")) if r["slice"] == "all"}


def correction():
    m = metrics()
    ks = [1, 2, 3, 5]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, n in zip(axes, (1, 3)):
        series = {arm: [100 * float(m[(arm, n, k)]["correction_at5"]) for k in ks] for arm in ("hipporag", "dense")}
        for arm, color, marker, label in (("hipporag", ACCENT, "o", "HippoRAG 2"), ("dense", GRAY, "s", "dense")):
            ys, other = series[arm], series["dense" if arm == "hipporag" else "hipporag"]
            ax.plot(ks, ys, color=color, lw=2.5, marker=marker, ms=8, mec="white", mew=1.5)
            up0, up1 = ys[0] >= other[0], ys[-1] >= other[-1]      # the higher series is labelled above, the lower below
            ax.annotate(f"{label} {ys[0]:.0f}%", (ks[0], ys[0]), xytext=(-4, 12 if up0 else -22), textcoords="offset points", color=INK, fontsize=12)
            ax.annotate(f"{ys[-1]:.0f}%", (ks[-1], ys[-1]), xytext=(-12, 12 if up1 else -22), textcoords="offset points", color=INK, fontsize=12)
        ax.set_title(f"{n} old cop{'y' if n == 1 else 'ies'}", loc="left", fontsize=14, color=INK)
        ax.set_xticks(ks)
        ax.set_xlim(0.6, 5.9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("corrections added (k)")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("correction in top 5 (%)")
    fig.tight_layout()
    fig.savefig(OUT / "correction.pdf")
    plt.close(fig)


def funnel():
    p = json.loads((A / "phase_b.json").read_text())
    e = next(x for x in p["funnel"] if (x["n"], x["k"]) == (1, 1))
    steps = [("questions", e["N"]), ("correction's fact among\nthe 5 candidate facts", e["new_in_candidates"]),
             ("kept by the filter", e["new_kept"]), ("old fact also kept\n(the fix can act)", e["both_kept"])]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (label, v) in enumerate(steps):
        y = len(steps) - 1 - i
        ax.barh(y, v, height=0.62, color=ACCENT if i else GRAY)
        ax.text(v + 1.2, y, str(v), va="center", fontsize=20, color=INK, fontweight="bold")
        ax.text(-1.5, y, label, va="center", ha="right", fontsize=12, color=INK)
    ax.set_xlim(0, e["N"] + 10)
    ax.set_ylim(-0.6, len(steps) - 0.4)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "funnel.pdf")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    correction()
    funnel()
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
