"""Results-independent figures for the paper: vector PDF plus PNG at 2x (300 dpi) for slides.

  pipeline.{pdf,png}   HippoRAG 2 retrieval as stages A-E, with the failure point at each stage
  toy_graph.{pdf,png}  the toy graph of the theory section (n = 3 old passages, k = 2 new passages)
  repro_gap.{pdf,png}  reproduction: HippoRAG 2 minus dense gap, n = 100 slice vs n = 500 vs the paper

Reproduction numbers are copied from PROGRESS.md (Session 4); nothing here reads extension results.
Palette: the dataviz skill's reference palette (slot 1 blue, slot 2 orange; gray for reference/neutral marks).

    .venv/bin/python paper/figs/make_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, AXIS, SURFACE, NEUTRAL = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#c3c2b7"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "pdf.fonttype": 42})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", facecolor=SURFACE, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ pipeline A-E -----------------------
def pipeline():
    stages = [
        ("A", "Fact\ncandidates", "top 5 facts by\nquery–fact\nsimilarity",
         "new fact (s, r, o′)\nnot in the top 5"),
        ("B", "Recognition\nfilter", "one LLM call\nkeeps relevant\nfacts; none kept\n→ dense retrieval",
         "filter drops\nthe new fact"),
        ("C", "Seeds", "kept-fact phrases:\nscore ÷ #passages,\ntop 5 phrases;\npassages: 0.05×dense",
         "o′ gets no\nreset mass"),
        ("D", "Personalized\nPageRank", "damping 0.5,\nundirected,\nweighted edges",
         "margin favours\nthe old passages"),
        ("E", "Top 5\npassages", "passages ranked\nby PPR score",
         "outranks or ties\nold, but crowded\nout of the top 5"),
    ]
    w, gap = 1.62, 0.42
    fig, ax = plt.subplots(figsize=(7.2, 3.0), facecolor=SURFACE)
    ax.set_xlim(0, 0.2 + 5 * w + 4 * gap)
    ax.set_ylim(-0.45, 4.95)
    ax.axis("off")
    for i, (letter, title, body, fail) in enumerate(stages):
        x0 = 0.1 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x0, 1.75), w, 2.55, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor="#ffffff", edgecolor=AXIS, linewidth=0.9))
        ax.text(x0 + 0.12, 3.98, letter, fontsize=11, fontweight="bold", color=BLUE, va="center")
        ax.text(x0 + 0.42, 3.98, title, fontsize=7.2, fontweight="bold", va="center", linespacing=1.05)
        ax.text(x0 + w / 2, 2.6, body, fontsize=6.4, color=INK2, ha="center", va="center", linespacing=1.25)
        ax.add_patch(FancyBboxPatch((x0, 0.15), w, 1.1, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor="#fdf0ea", edgecolor=ORANGE, linewidth=0.9))
        ax.text(x0 + w / 2, 0.7, fail, fontsize=6.3, ha="center", va="center", linespacing=1.2)
        ax.add_patch(FancyArrowPatch((x0 + w / 2, 1.72), (x0 + w / 2, 1.3), arrowstyle="-|>", mutation_scale=7,
                                     color=ORANGE, linewidth=0.9))
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch((x0 + w + 0.03, 2.6), (x0 + w + gap - 0.03, 2.6), arrowstyle="-|>",
                                         mutation_scale=8, color=INK2, linewidth=1.0))
    ax.text(0.1, 4.75, "Retrieval stage", fontsize=7, color=INK2)
    ax.text(0.1, -0.3, "Failure point for a correction (first-failure attribution, orange)", fontsize=7, color=INK2)
    # where the contradiction-aware fix acts: after the filter (B), before the seeds (C)
    xb = 0.1 + 1 * (w + gap) + w + gap / 2
    ax.annotate("fix acts here: drop the superseded fact", xy=(xb, 2.8), xytext=(xb, 4.68), fontsize=6.4,
                color=AQUA, ha="center", va="center", arrowprops=dict(arrowstyle="-|>", color=AQUA, linewidth=0.9))
    save(fig, "pipeline")


# ------------------------------------------------------------------ toy graph --------------------------
def toy_graph():
    fig, ax = plt.subplots(figsize=(3.6, 2.7), facecolor=SURFACE)
    ax.set_xlim(-1.45, 5.45)
    ax.set_ylim(-0.4, 3.3)
    ax.axis("off")
    pos = {"e": (2.0, 2.75), "D": (0.7, 0.2), "M": (3.3, 0.2)}
    # passage nodes placed clear of the straight e-D and e-M relation edges (which cross y = 1.45 at x ~ 1.34 / 2.66)
    olds = [(-0.3 + 0.55 * i, 1.45) for i in range(3)]
    news = [(3.2 + 0.55 * j, 1.45) for j in range(2)]
    for p in olds:
        for tgt in ("e", "D"):
            ax.plot(*zip(p, pos[tgt]), color=AXIS, linewidth=1.0, zorder=1)
    for p in news:
        for tgt in ("e", "M"):
            ax.plot(*zip(p, pos[tgt]), color=AXIS, linewidth=1.0, zorder=1)
    # Graph B relation edges, count-weighted
    ax.plot(*zip(pos["e"], pos["D"]), color=BLUE, linewidth=2.2, linestyle=(0, (4, 2)), zorder=0)
    ax.plot(*zip(pos["e"], pos["M"]), color=ORANGE, linewidth=1.6, linestyle=(0, (4, 2)), zorder=0)
    ax.text(1.2, 0.62, "weight n", fontsize=6.5, color=BLUE, ha="left", va="bottom", rotation=63)
    ax.text(2.8, 0.62, "weight k", fontsize=6.5, color=ORANGE, ha="right", va="bottom", rotation=-63)
    for p in olds:
        ax.scatter(*p, s=150, marker="s", color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for p in news:
        ax.scatter(*p, s=150, marker="s", color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for name, c in (("e", INK2), ("D", BLUE), ("M", ORANGE)):
        ax.scatter(*pos[name], s=330, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.text(*pos[name], name, color="white", fontsize=8, fontweight="bold", ha="center", va="center", zorder=4)
    ax.text(-0.6, 1.45, "n old\npassages\n(e, D)", fontsize=6.3, ha="right", va="center", color=INK)
    ax.text(4.05, 1.45, "k new\npassages\n(e, M)", fontsize=6.3, ha="left", va="center", color=INK)
    ax.text(2.0, 3.12, "shared subject", fontsize=6.5, ha="center", color=INK2)
    ax.plot([-1.2, -0.85], [-0.28, -0.28], color=AXIS, linewidth=1.0)
    ax.text(-0.78, -0.28, "passage edge (weight 1)", fontsize=6, va="center", color=INK2)
    ax.plot([2.0, 2.35], [-0.28, -0.28], color=INK2, linewidth=1.6, linestyle=(0, (4, 2)))
    ax.text(2.42, -0.28, "relation edge (Graph B)", fontsize=6, va="center", color=INK2)
    save(fig, "toy_graph")


# ------------------------------------------------------------------ reproduction gap -------------------
# From PROGRESS.md, Session 4. n=100 slice = first 100 questions of the n=500 runs (paired bootstrap, 10,000
# resamples, seed 0). The logged n=100 run itself: Recall@5 +4.50, F1 +8.18 (no CI; per-query data not kept).
REPRO = {
    "Recall@5": [("n = 100 (slice)", 4.50, -0.50, 9.67), ("n = 500", 5.90, 3.73, 8.00), ("Paper, n = 1,000", 5.0, None, None)],
    "F1": [("n = 100 (slice)", 7.84, 0.49, 15.51), ("n = 500", 4.66, 1.52, 7.69), ("Paper, n = 1,000", 2.9, None, None)],
}


def repro_gap():
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 1.9), sharey=True, facecolor=SURFACE)
    for ax, (metric, rows) in zip(axes, REPRO.items()):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
        ax.xaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.axvline(0, color=INK2, linewidth=0.8)
        for i, (label, gap, lo, hi) in enumerate(rows):
            yv = len(rows) - 1 - i
            if lo is not None:
                ax.plot([lo, hi], [yv, yv], color=BLUE, linewidth=2, solid_capstyle="round")
                ax.scatter(gap, yv, s=48, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3)
            else:
                ax.scatter(gap, yv, s=48, marker="D", color=NEUTRAL, edgecolor=INK2, linewidth=0.8, zorder=3)
            ax.text(gap, yv + 0.28, f"{gap:+.1f}", fontsize=7, ha="center", color=INK)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r[0] for r in reversed(rows)])
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(-0.6, len(rows) - 0.3)
        ax.set_title(f"{metric} gap (HippoRAG 2 − dense), points", fontsize=8, loc="left", color=INK)
    fig.text(0.01, -0.06, "Blue: this reproduction (gpt-4o-mini + text-embedding-3-small) with paired-bootstrap 95% CI. "
             "Gray diamond: the paper (Llama-3.3-70B + NV-Embed-v2).", fontsize=6.3, color=INK2)
    fig.tight_layout()
    save(fig, "repro_gap")


if __name__ == "__main__":
    pipeline()
    toy_graph()
    repro_gap()
    print("wrote", sorted(p.name for p in OUT.glob("*.p*")))
