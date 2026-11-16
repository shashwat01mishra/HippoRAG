# Speaker notes: Presentation 2 (18 Nov 2026, 15 min)

Build: `.venv/bin/python deck/make_figs.py && cd deck && tectonic -X compile deck.tex`. Target: about 11.5 minutes of slides plus 3 minutes of demo. Slides 8, 9 and the "why" on slide 11 use exploratory analyses (not in the prediction); say so.

**Source letters** (every number on a slide has one):
R = `results/musique_n500/bootstrap_n500.txt` · S = `analysis/grid_v5_final/summary.md` · U = `analysis/grid_v5_final/followup.md` · B = `analysis/grid_v5_final/bootstrap.csv` · P = `analysis/grid_v5_final/phase_b.md` · T = `paper/sections/reproduction.tex` · G = `demo/graph_stats.md` · Q = `demo/traces/q193.md` · L = `PROGRESS.md` · F = `experiments/extension/data/review_reasons.md`

---

## 1. Title (30 s)
- Say the claim in one breath: stale copies of an old fact cost HippoRAG 2 about 12 points of correction recall and cost dense search about 1.
- Numbers behind the sentence: −11.7 pts vs −0.7 pts, interaction −11.0 [−16.7, −6.0] (U §1).

## 2. Memory must be corrected, not just grow (45 s)
- The paper calls itself non-parametric continual learning. Its continual-learning experiment adds passages and checks that performance holds.
- A memory also has to handle a changed fact. The old passage stays in the index, so retrieval has to prefer the new one.
- The slide cites §6.3, "Robustness to Corpus Expansion" (section number and title supplied by me; no file in this repo contains them).

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

## 7. Stale copies hurt the graph, not dense (1.5 min) — lead result
- One sentence: add two more copies of the old passage, and HippoRAG 2 loses 11.7 points of correction@5 [−17.0, −6.7]; dense loses 0.7 [−1.7, 0.0] (P; U §1).
- The interaction, HippoRAG 2's change minus dense's: −11.0 points [−16.7, −6.0]. It excludes 0 at every k (U §1).
- Per question: HippoRAG 2 is worse for 18 and better for 0; dense is worse for 2 (U §1).
- Chart: n = 1: HippoRAG 2 52 % → 43 %, dense 40 % → 40 %. n = 3: 36 % → 33 % vs 37 % → 40 % (S).
- Only then the overall comparison: 41.5 % vs 39.0 %, +2.5 points [−6.7, +11.3], no reliable difference (P).
- This was prediction item 4, and I predicted the opposite.

## 8. The last-hop fact is rarely a seed, old or new (1 min)
- Funnel at n = 1, k = 1: 75 → 9 → 8 → 7 (P, funnel).
- The key comparison: before any correction, the old fact is among the 5 candidates for 9 of 75 as well, at n = 1 and n = 3 (U §2). So "not a candidate" is the normal state, not something that happens to corrections.
- Without its fact, the old passage is still in the top 5 for 34 of 66 questions (U §2). Passages mostly get there by their own seed and the graph.
- Exploratory: this comparison was not in the prediction. Say so.

## 9. The fix acts at the seed stage. Corrections don't. (1 min)
- 249 corrections reach the top 5 across the 8 cells. 71 had their fact as a candidate. 114 were also in the dense top 5, so their own passage seed (0.05 × dense similarity) is enough. 64 were outside the dense top 5 and were lifted by graph spread (U §2, "Route").
- For the 178 non-candidate ones, the passage's own seed is a median 68 % of its PageRank score (U §2).
- The fix removes the older of two conflicting seed facts. Both facts are seeded for 7 of 75 questions (P), and those already succeed. Result: +0.2 points [0.0, +0.5] (P).
- Where it fires it works: old seed removed 7 of 7, correction outranks old 7 of 7; stale passages in the top 5 at n = 3, k = 5 fall 0.61 → 0.41 (P, B).
- Exploratory (the route breakdown).

## 10. Prediction committed 460c50a, 16 Nov 18:59 IST (1 min)
- Hash and time: `git log -1 460c50a`. Grid sealed 9 Nov; seal re-checked 26 of 26 before opening (L).
- Scorecard: 5 misses, 1 hit (`RESULTS_BRIEF.md` §2). "Old wins 33 of 56" is at tolerance 0 where both facts were kept (P).
- The falsifier: I wrote that my account is wrong if the filter keeps more than 80 %. It kept 8 of 9, 89 % (P). Say it plainly: the account was wrong.
- Caveat to offer before being asked: 9 questions, CI 67–100 % (P).

## 11. Limits and next (45 s)
- 9 and 7 questions carry the filter and fix results (P). No dates on passages. Exact-duplicate copies. N = 75, one dataset, one LLM.
- Open question: why copies hurt the graph. In the 35 records lost at n = 3 (18 questions), an old passage is in the top 5 in 19 and the correction then sits at rank 6–10 in all 19. The old-vs-new order follows dense similarity (ρ = +0.91, same sign in 34 of 35), not node degree (ρ = +0.14, p = 0.43). o′ absent vs present: −8.1 vs −15.7 points, difference +7.6 [−2.6, +18.2] (U §3). All exploratory.
- Next: `linking_top_k` 5 → 20.

---

## Backup slides
- **Competing methods.** Descriptions are qualitative, from the papers cited in `paper/refs.bib`; no numbers.
- **Recall@k vs precision.** Contamination@5 at k = 0, n = 3: HippoRAG 2 1.43, dense 0.99 (S).
- **PPR maths.** d = 0.5 (`src/hipporag/utils/config_utils.py:192`); mean walk d/(1−d) is 1 step at 0.5 and 0.85/0.15 ≈ 5.7 at 0.85 (arithmetic). Reset split 2.0 % / 98.0 % (Q).
- **Metric definitions.** `experiments/extension/analysis.py:44–68`.
- **Cost.** ₹17.41 and ₹36.44 are actual key usage; ₹3.60, ₹33.29 and ₹0.03 are estimates at list × 1.1 (L, Sessions 4, 6, 8).
- **Long-context reader.** Answers o′ / o / neither: (1,1) 7 / 41 / 27; (1,5) 26 / 19 / 30; (3,1) 1 / 43 / 31; (3,5) 16 / 32 / 26, one "both" (P).
