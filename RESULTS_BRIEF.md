# Results brief: does HippoRAG 2's memory accept a correction?

Written 2026-11-16, after the prediction commit `460c50a` (2026-11-16 18:59:47 IST). The sealed grid `grid_v5_20261109` matched its sha256 seal (26 of 26 files). N = 75 hand-screened swaps; grid n ∈ {1, 3} old copies × k ∈ {0, 1, 2, 3, 5} corrections.

**Sources**, cited by letter after each number:

| | File |
|---|---|
| **R** | `results/musique_n500/bootstrap_n500.txt` |
| **S** | `analysis/grid_v5_final/summary.md` (same numbers in `metrics.csv`, `attribution.csv`) |
| **B** | `analysis/grid_v5_final/bootstrap.csv` |
| **P** | `analysis/grid_v5_final/phase_b.md` (full precision in `phase_b.json`) |
| **M** | `analysis/grid_v5_final_minus_specialist/phase_b.md` |
| **T** | `paper/sections/reproduction.tex` (the paper's numbers, with its table numbers) |

All intervals are paired-bootstrap 95 % CIs over questions (10,000 resamples, seed 0). "correction@5" = a corrected passage is in the top 5. "contamination@5" = mean number of old passages in the top 5.

## 1. Headline numbers

**Reproduction (MuSiQue, first 500 questions).** HippoRAG 2 beats dense retrieval with the same embedder.

| | HippoRAG 2 | dense | gap [95 % CI] | paper's gpt-4o-mini gap (T: App. C, Tables 8–9) |
|---|---|---|---|---|
| Recall@5 | 62.00 | 56.10 | +5.90 [+3.73, +8.00] | +4.5 |
| F1 | 44.93 | 40.27 | +4.66 [+1.52, +7.69] | +3.3 |

(R; paper column T.) The paper's gaps fall inside our intervals. Our absolute numbers are lower than the paper's (T: 74.2 vs 69.7 Recall@5), with a different embedder.

**Extension: correction@5, pooled over the 8 cells with k ≥ 1.**

| | dense | HippoRAG 2 | HippoRAG 2 + fix | HippoRAG 2 − dense | fix − HippoRAG 2 |
|---|---|---|---|---|---|
| all 8 cells | 39.0 % [28.3, 49.7] | 41.5 % [31.3, 51.5] | 41.7 % [31.5, 51.8] | +2.5 pts [−6.7, +11.3] | +0.2 pts [+0.0, +0.5] |
| n = 1 | 39.3 % | 47.3 % | 47.3 % | +8.0 pts [−2.0, +18.0] | +0.0 |
| n = 3 | 38.7 % | 35.7 % | 36.0 % | −3.0 pts [−12.0, +5.7] | +0.3 pts [+0.0, +1.0] |

(P, "Pooled correction@5".) In plain terms:

- Both systems put the correction in the top 5 for roughly 4 questions in 10. Adding more corrections does not help: HippoRAG 2 goes from 52 % at k = 1 to 43 % at k = 5 (n = 1), dense stays at 39–40 % (S).
- HippoRAG 2 is not reliably better than dense at accepting corrections. Its best cell is n = 1, k = 1: 52 % vs 40 %, +12 pts [0, +24] (B). The pooled difference includes 0.
- **Stale copies hurt HippoRAG 2 and not dense.** Going from 1 to 3 old copies changes correction@5 by −11.7 pts [−17.0, −6.7] for HippoRAG 2 and −0.7 pts [−1.7, 0.0] for dense; the difference is −11.0 pts [−16.7, −6.0] (P, "Effect of stale copies").
- Before any correction (k = 0), HippoRAG 2 retrieves the original passage more often than dense: 0.57 vs 0.36 at n = 1 (S, contamination@5). So at n = 1 the correction (52 %) is retrieved almost as often as the original it replaces (57 %); the ceiling is how retrievable that passage is, not resistance to the edit.

**With and without the 8 specialist-knowledge rows (19, 25, 29, 45, 91, 100, 109, 114).**

| | N | dense | HippoRAG 2 | HippoRAG 2 − dense | n = 1 → 3 change, HippoRAG 2 | same, dense | fix − HippoRAG 2 | source |
|---|---|---|---|---|---|---|---|---|
| all kept | 75 | 39.0 % | 41.5 % | +2.5 pts [−6.7, +11.3] | −11.7 pts [−17.0, −6.7] | −0.7 pts | +0.2 pts | P |
| without the 8 | 67 | 39.2 % | 38.4 % | −0.7 pts [−9.9, +8.6] | −11.2 pts [−17.2, −6.0] | −0.7 pts | +0.0 pts | M |

The conclusions do not change: no reliable HippoRAG-vs-dense difference, the same stale-copy penalty, no effect of the fix. The small pooled advantage of HippoRAG 2 disappears without the 8 rows.

## 2. The 8 prediction items

| # | Prediction (`notes/prediction.md`) | Actual | Verdict |
|---|---|---|---|
| 1 | The filter keeps the correction in 30–60 % of questions | When the correction's fact reaches the filter it is kept in 8 of 9 questions (89 %), in every cell. Counted over all questions it is kept in 8 of 75 (11 %), because it reaches the filter for only 9 (P, "Filter keep rate") | **Miss** on both readings |
| 2 | With both facts seeded: a near-tie decided by dense similarity | 56 records from 7 questions. At 1 % tolerance: 22 new wins, 9 near-ties, 25 old wins. Median relative margin 4.4 %. The PPR winner matches the dense winner in 20 of 56 (36 %) (P, "Records where the filter kept both") | **Miss**: not a tie, and not decided by dense |
| 3 | Main failure stage: B, the filter | Stage A in every cell: 36–49 of 75 questions fail because the correction's fact is not among the 5 candidate facts. Stage B: 0 (S, attribution table) | **Miss** |
| 4 | As n grows, HippoRAG's correction@5 drops slower than dense's | It drops faster: −11.7 pts vs −0.7 pts (P) | **Miss** (opposite direction) |
| 5a | The fix raises correction@5 by +1–5 pts | +0.0 in 7 of 8 cells, +1.3 pts at n = 3, k = 5; pooled +0.2 pts [0.0, +0.5] (B, P) | **Miss** (below the range) |
| 5b | Unchanged-fact Recall@5 changes by about 0 | At k = 0 the fix never fires and the top 5 is identical in 75/75 questions. With k ≥ 1, recall of the other gold passages changes in 1 record at (1,1) and 1 at (1,2): 0.700 → 0.687. No non-target fact was dropped (P, "Fix vs no fix"; S, collateral table) | **Hit** |
| 6 | Account is wrong if the filter keeps > 80 %, or the fix adds > 10 pts | The filter keeps 89 % of the corrections it sees (8/9; per-question CI 67–100 %, 9 questions). The fix adds +0.2 pts (P) | **First falsifier triggered.** The account "the filter is the bottleneck" is wrong |
| 7 | When the model knows o, the filter keeps the correction less often | Knows o: 5 of 6 kept. Does not know: 3 of 3 kept (P). The one dropped correction is a "knows" question, and it is one of the 8 specialist rows (M: 7/7 kept without them) | **Untestable** at 9 questions; direction matches, by one question |
| 8 | Rare vs common o′: untested | Still untested: the ≥ 10 bin has 9 swaps (S, header) | As stated |

Score: 1 hit (5b), 5 misses (1, 2, 3, 4, 5a), 1 untestable (7), 1 untested (8), and the prediction's own falsifier fired (6).

## 3. Attribution

The three mechanisms from the theory, mapped to the pipeline stages:

| Mechanism | Stages | Failures attributed (first failing stage, per cell of 75) | Source |
|---|---|---|---|
| **Seed-slot exclusion**: the correction never gets a seed | A (not a candidate), B (filtered), C (o′ not seeded) | A: 36, 37, 42, 43 (n = 1; k = 1, 2, 3, 5) and 48, 47, 48, 49 (n = 3). B: 0. C: 0 | S |
| **Graph asymmetry**: seeded, but the old passage scores higher | D | 1, at n = 3, k = 5 at tolerance 0 (it becomes a tie at 1 %) | S |
| **Top-5 contamination**: outranks or ties, but crowded out | E | 0 (1 at n = 3, k = 5 at tolerance ≥ 1 %) | S |

So by the first-failure rule, essentially every failure is seed-slot exclusion, and all of it at stage A. Details:

- **The exclusion happens before the filter.** HippoRAG 2 sends only the top 5 query-to-triple matches to the filter. The correction's fact is among them for 9 of 75 questions. The old fact is among them for only 9 of 75 even before any correction (P, funnel, k = 0). These are multi-hop questions and the swapped fact is almost always the last hop, so the question text matches first-hop facts instead. This is a property of the question type, not of the counterfactual.
- **When the fact is a candidate, the correction is retrieved**: 9 of 9 in seven cells, 8 of 9 at n = 3, k = 5 (P, funnel).
- **When it is not a candidate, HippoRAG 2 relies on passage seeds and the graph.** There it retrieves the correction in 45 % of questions at n = 1, k = 1, falling to 26 % at n = 3, k = 5; dense gets 30–33 % on the same questions (P, funnel).
- **The first-failure rule hides a second effect.** Among the questions HippoRAG 2 loses when going from n = 1 to n = 3 (12, 10, 6 and 7 questions for k = 1, 2, 3, 5; none gained), the old passage outranks the correction in 10, 8, 4 and 5 (P, "failures"). That pattern is what graph asymmetry or contamination would look like, but the rule assigns these to A because A fails first. I can't separate the two from these records.
- Most failures are hard for both systems: dense also fails on 30 of HippoRAG 2's 36 failures at n = 1, k = 1 (P, "failures").

## 4. What the seed-stage fix changes

The fix drops the older of two kept facts that share subject and relation.

- It fires for 7 questions, in every k ≥ 1 cell: exactly the ones where both facts survive the filter (P, "Fix vs no fix").
- Where it fires it does what it should at the seed level: the old object loses its seed in 7 of 7, and the correction outranks the old passage in 7 of 7 (before the fix: 2 of 7 at n = 1, k = 1) (P).
- That does not change correction@5, because in those 7 questions the correction was already in the top 5 (7 → 7). The one gain is at n = 3, k = 5 (6 → 7) (P).
- It does remove stale passages from the top 5 when there are many corrections: contamination@5 at n = 3, k = 5 falls from 0.61 to 0.41, −0.20 [−0.40, −0.04]; at n = 1, k = 5 from 0.20 to 0.13, −0.07 [−0.13, −0.01]; no change at k = 1 (B).
- No collateral: 0 non-target facts dropped (S).

In short: the fix is correct but aimed at a stage that 9 in 10 questions never reach.

## 5. Surprises

1. **The bottleneck is the 5-candidate linking step, not the filter.** I expected gpt-4o-mini to reject counterfactuals. It kept 8 of the 9 it saw (P).
2. **More corrections do not help HippoRAG 2**: 52 % → 43 % from k = 1 to k = 5 at n = 1 (S).
3. **Stale copies cost HippoRAG 2 about 12 points and dense about 1** (P). The prediction said the opposite.
4. **The reader rarely adopts the correction even when it sees everything.** With all passages in context, the reader answers o′ in 7 of 75 questions at (1,1), 26 at (1,5), 1 at (3,1) and 16 at (3,5); it answers the old o in 41, 19, 43 and 32 (P, "Long-context reader"). So retrieval is not the only obstacle.
5. Both-kept cases are not ties: old wins 33 of 56 at tolerance 0 (P).

## 6. Limitations

- **9 questions carry the filter and fix findings.** The filter keep rate (8/9) has a CI of 67–100 %, and item 7 rests on a single question.
- **Nothing tells the system the correction is newer.** Injected passages carry no date; "correction" is defined only by insertion order, which neither PPR nor the reader sees (only the fix uses it). The long-context result should be read with that in mind: the reader has no reason to prefer o′.
- **Injected copies are exact duplicates** apart from the title line, so dense scores of copies are nearly equal. Paraphrased copies were cut from scope.
- **Counterfactuals are synthetic** (generated o′, triples copied with o replaced, not re-extracted), and contradiction detection is an oracle (exact subject + relation match).
- **Screening was done by Claude in two passes**, with 8 specialist-knowledge keeps; the sensitivity row above shows the conclusions hold without them.
- **N = 75, one dataset, one LLM in every role** (gpt-4o-mini), top-5 linking as shipped (`linking_top_k = 5`).
- The o′-frequency question (item 8) could not be tested.

## 7. What I would do next

- Rerun with a larger `linking_top_k` (10, 20): if stage A is the bottleneck, correction@5 and the fix's effect should both rise. This needs new filter calls (paid).
- Change the attribution rule so a question can carry two labels (A and "old outranks new"), to measure the stale-copy effect directly.
- Give passages a date and test whether the reader then prefers the correction.
