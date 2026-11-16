# Speaker notes: Presentation 2 (18 Nov 2026, 15 min)

Build: `.venv/bin/python deck/make_figs.py && cd deck && tectonic -X compile deck.tex`. Target: about 11 minutes of slides plus 3 minutes of demo.

**Source letters** (every number on a slide has one):
R = `results/musique_n500/bootstrap_n500.txt` · S = `analysis/grid_v5_final/summary.md` · B = `analysis/grid_v5_final/bootstrap.csv` · P = `analysis/grid_v5_final/phase_b.md` · T = `paper/sections/reproduction.tex` · G = `demo/graph_stats.md` · Q = `demo/traces/q193.md` · L = `PROGRESS.md` · F = `experiments/extension/data/review_reasons.md`

---

## 1. Title (30 s)
- Say the claim in one breath: HippoRAG 2 retrieves better than dense search, but when a fact changes it accepts the correction no better, and extra stale copies hurt it more than they hurt dense.
- Numbers behind the sentence: "no better" = pooled correction@5 41.5 % vs 39.0 %, difference +2.5 pts [−6.7, +11.3] (P). "Stale copies hurt it more" = −11.7 pts vs −0.7 pts (P).

## 2. Memory must be corrected, not just grow (45 s)
- The paper calls itself non-parametric continual learning. Its continual-learning experiment adds passages and checks that performance holds.
- A memory also has to handle a changed fact. The old passage stays in the index, so retrieval has to prefer the new one.
- **Check before the talk:** the slide says "Section 6.3". That section number comes from my outline, not from a file in this repo. Open the paper and confirm it.

## 3. Pipeline, then LIVE DEMO (4 min in total)
- Walk the figure left to right: query → top 5 triples → LLM filter → seeds → Personalized PageRank → top 5 passages → reader.
- Index size: 11,656 passage nodes, 101,544 entity nodes, 322,183 edges (G).
- **Demo** (`demo/run_demo.py --q 193 --pause`, offline replay, instant):
  - Step 1: 5 candidate facts; the top one is about the wrong season (Adam Lambert, season 8) (Q).
  - Step 2: the filter keeps 2 of 5, the two that are about season 3 (Q).
  - Step 3: entity seeds are only 2.0 % of the reset mass; 98.0 % is spread over 11,655 passages at dense × 0.05 (Q).
  - Step 5: both gold passages in the top 5; dense has neither. Recall@5 1.00 vs 0.00 (Q).
  - Step 6: reader says "Third season.", gold is "season three": F1 0.50, a scoring artefact (Q).
- **Live tweak** (`--live --q 193 --damping 0.85 --passage_weight 0.5`): PPR top 10 becomes hub entities (united states, canada, ...), one gold passage drops out, Recall@5 1.00 → 0.50 (L, Session 8, steps 2–3). Cost about ₹0.03 with the reader, ₹0.00 with `--no_reader` (L).
- If the network fails: stay on replay; say the live mode exists.

## 4. The reproduction holds (1 min)
- 500 questions, both systems on identical passage vectors.
- Recall@5 62.00 vs 56.10: +5.90 [+3.73, +8.00]. F1 44.93 vs 40.27: +4.66 [+1.52, +7.69] (R).
- Paper's gpt-4o-mini rows: Recall@5 74.2 vs 69.7 (+4.5), F1 49.3 vs 46.0 (+3.3) (T, citing the paper's Appendix C, Tables 8 and 9). Both paper gaps are inside our intervals.
- Say plainly: I reproduce the gap, not the absolute numbers. Different embedder (text-embedding-3-small vs NV-Embed-v2).

## 5. Theory (1 min)
- Toy graph: one subject, old object with n passages, new object with k passages.
- If only the shared subject is seeded, every passage gets the same score, d/((1+d)(n+k)). Verified symbolically and against igraph to 2.2e-16 (L, Session 7).
- So repetition alone cannot make the old fact win. Resistance needs one of three things: no seed for the correction, graph asymmetry, or crowding of the top 5.

## 6. Design (1 min)
- One swap per gold passage: replace the answer object with a plausible false one. 120 generated, 75 kept after two screening passes (F).
- Grid: n ∈ {1, 3} old copies, k ∈ {0, 1, 2, 3, 5} corrections; HippoRAG 2 and dense on the same index.
- Blind protocol: the grid ran and was sealed by sha256 on 9 Nov (L, "Seal"). Prediction committed as `460c50a` on 16 Nov, 18:59 IST (`git log -1 460c50a`). Seal re-checked, 26 of 26 files match (L, Session 8). Only then were results opened.
- Be upfront: the prediction was written after the run but before looking; the seal is what makes that checkable.

## 7. Correction in the top 5 (1.5 min)
- Read the chart: n = 1: HippoRAG 2 52 % → 43 %, dense 40 % → 40 %. n = 3: HippoRAG 2 36 % → 33 %, dense 37 % → 40 % (S).
- Best case for HippoRAG 2 is n = 1, k = 1: +12 pts [0, +24] (B). Pooled over all cells the difference is +2.5 pts [−6.7, +11.3] (P).
- Stale copies: −11.7 pts [−17.0, −6.7] for HippoRAG 2, −0.7 for dense (P).
- More corrections do not help.
- Context: before any correction HippoRAG 2 finds the original passage 57 % of the time at n = 1, dense 36 % (S, contamination@5 at k = 0). The correction is found about as often as the original was.

## 8. Why (1.5 min)
- Funnel at n = 1, k = 1: 75 questions → correction's fact among the 5 candidates in 9 → kept by the filter in 8 → old fact also kept in 7 (P, funnel).
- Failures: 36 of 36 at (1,1) are "not a candidate"; across the grid every failure but one (S, attribution).
- Why so few candidates: multi-hop questions; the swapped fact is the last hop, and the question text matches first-hop facts. The old fact is a candidate in only 9 of 75 even before any correction (P, k = 0 rows).
- The fix fires in those 7 questions. It removes the old seed in 7 of 7 and makes the correction outrank the old passage in 7 of 7, but they were already in the top 5, so correction@5 moves +0.2 pts [0.0, +0.5] (P, B). It does lower stale passages in the top 5 at k = 5: 0.61 → 0.41 at n = 3 (B).

## 9. Prediction vs outcome (1 min)
- Five misses, one hit (P, S; table in `RESULTS_BRIEF.md` §2). My account was "the filter is the bottleneck"; it kept 8 of 9. My own falsifier (keeps > 80 %) fired.
- "Old wins 33 of 56" is at tolerance 0, in records where both facts were kept (P).
- Limits: the filter result rests on 9 questions (CI 67–100 %, P); passages carry no date; N = 75.
- Next: raise `linking_top_k` from 5 to 20 and rerun.

---

## Backup slides
- **Competing methods.** Descriptions are qualitative, from the papers cited in `paper/refs.bib`; no numbers.
- **Recall@k vs precision.** Contamination@5 at k = 0, n = 3: HippoRAG 2 1.43, dense 0.99 (S).
- **PPR maths.** d = 0.5 (`src/hipporag/utils/config_utils.py:192`); mean walk d/(1−d) is 1 step at 0.5 and 0.85/0.15 ≈ 5.7 at 0.85 (arithmetic). Reset split 2.0 % / 98.0 % (Q).
- **Metric definitions.** `experiments/extension/analysis.py:44–68`.
- **Cost.** ₹17.41 and ₹36.44 are actual key usage; ₹3.60, ₹33.29 and ₹0.03 are estimates at list × 1.1 (L, Sessions 4, 6, 8).
- **Long-context reader.** Answers o′ / o / neither: (1,1) 7 / 41 / 27; (1,5) 26 / 19 / 30; (3,1) 1 / 43 / 31; (3,5) 16 / 32 / 26, one "both" (P).
