# Paper to-do (not applied to `paper/`)

`paper/` is not edited in this phase (Presentation 2 prep rule). These items wait for the final paper.

## Add MemoryAgentBench to `paper/refs.bib` and Related Work

- Hu, Y., Wang, Y., and McAuley, J. (2025). *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions* (MemoryAgentBench). arXiv 2507.05257. First submitted 7 Jul 2025; Hu and Wang are equal contributors.
- Numbers, checked on 17 Nov 2026 against the arXiv HTML by a fetch of v1 (https://arxiv.org/html/2507.05257v1) and v4 (https://arxiv.org/html/2507.05257v4):
  - **v1, Table 2 ("Overall Performance Comparison")**, Conflict Resolution columns FactCon-SH / FactCon-MH, all agents with a GPT-4o-mini backbone:
    - HippoRAG-v2: single-hop **54.0**, multi-hop **5.0**
    - NV-Embed-v2: single-hop **55.0**, multi-hop **6.0**
  - **v4 (latest, 28 Jun 2026), Table 3**: the category is renamed "Selective Forgetting" (columns FC-SH / FC-MH). HippoRAG-v2 is still 54.0 / 5.0. NV-Embed-v2 has no row of its own in v4; it is named only as HippoRAG-v2's embedder (App. E.5, F.2).
  - So cite **v1, Table 2** for the 54.0 vs 55.0 and 5.0 vs 6.0 comparison, and say so.
- What it does not do (checked in v1 and v4): it does not attribute failures to retrieval stages (no mention of candidate linking, the filter or PageRank), and it does not vary the number of stale copies of an outdated fact; the only variable is context length (v4: 6K, 32K, 64K, 262K; v1: 32K, 64K, 262K). That is the gap this project fills.

## HippoRAG 2 §6.3

- §6.3 is titled "Robustness to Corpus Expansion". It only adds passages and never changes a fact. Confirmed by the user against the arXiv HTML on 17 Nov 2026. Use this wording in Related Work / Introduction when motivating correction rather than growth.

## Theory section

- `paper/sections/theory.tex` gives the Graph B margin (with fact edges): x − y = 2(1−d)/(4−d²)·[d(r_D/n − r_M/k) + 2(r_o − r_m)]. The deck uses the Graph A margin (passage edges only), 2(1−d)/(2−d²)·[(r_o − r_m) + d(r_D/n − r_M/k)] (PROGRESS.md, Session 7). Both make the same point: the subject's seed r_e cancels, and old versus new is set by the passage seeds and the object seeds. State which graph each formula is for.
- Add the empirical check: the PPR margin follows the dense-cosine margin (passage-seed term) in the 35 records lost at n = 3 (`analysis/grid_v5_final/followup.md` §3).

## Precision

- Add a footnote or appendix line: in the first 500 questions, 269 have 2 gold passages, 149 have 3 and 82 have 4, so a perfect retriever's precision@5 is 52.52; HippoRAG 2 30.12, dense 27.72 (`results/musique_n500/precision_at5.txt`).
