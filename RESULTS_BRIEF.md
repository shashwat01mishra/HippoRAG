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
| **U** | `analysis/grid_v5_final/followup.md` (follow-up analyses; full precision in `followup.json`) |

All intervals are paired-bootstrap 95 % CIs over questions (10,000 resamples, seed 0). "correction@5" = a corrected passage is in the top 5. "contamination@5" = mean number of old passages in the top 5.

## 1. Headline numbers

**Reproduction (MuSiQue, first 500 questions).** HippoRAG 2 beats dense retrieval with the same embedder.

| | HippoRAG 2 | dense | gap [95 % CI] | paper's gpt-4o-mini gap (T: App. C, Tables 8–9) |
|---|---|---|---|---|
| Recall@5 | 62.00 | 56.10 | +5.90 [+3.73, +8.00] | +4.5 |
| F1 | 44.93 | 40.27 | +4.66 [+1.52, +7.69] | +3.3 |

(R; paper column T.) The paper's gaps fall inside our intervals. Our absolute numbers are lower than the paper's (T: 74.2 vs 69.7 Recall@5), with a different embedder.

**Extension, main finding: stale copies hurt the graph and not dense.** Going from 1 to 3 old copies changes correction@5 by −11.7 pts [−17.0, −6.7] for HippoRAG 2 and by −0.7 pts [−1.7, 0.0] for dense. The interaction (HippoRAG 2's change minus dense's) is **−11.0 pts [−16.7, −6.0]**, and it excludes 0 at every k: −13.3 [−22.7, −4.0], −13.3 [−21.3, −6.7], −8.0 [−14.7, −2.7], −9.3 [−16.0, −4.0] for k = 1, 2, 3, 5. HippoRAG 2 gets worse for 18 questions and better for none; dense gets worse for 2 (U, §1). This is the direct test of prediction item 4, which said the opposite.

**Extension: correction@5, pooled over the 8 cells with k ≥ 1.**

| | dense | HippoRAG 2 | HippoRAG 2 + fix | HippoRAG 2 − dense | fix − HippoRAG 2 |
|---|---|---|---|---|---|
| all 8 cells | 39.0 % [28.3, 49.7] | 41.5 % [31.3, 51.5] | 41.7 % [31.5, 51.8] | +2.5 pts [−6.7, +11.3] | +0.2 pts [+0.0, +0.5] |
| n = 1 | 39.3 % | 47.3 % | 47.3 % | +8.0 pts [−2.0, +18.0] | +0.0 |
| n = 3 | 38.7 % | 35.7 % | 36.0 % | −3.0 pts [−12.0, +5.7] | +0.3 pts [+0.0, +1.0] |

(P, "Pooled correction@5".) In plain terms:

- Both systems put the correction in the top 5 for roughly 4 questions in 10. Adding more corrections does not help: HippoRAG 2 goes from 52 % at k = 1 to 43 % at k = 5 (n = 1), dense stays at 39–40 % (S).
- HippoRAG 2 is not reliably better than dense at accepting corrections. Its best cell is n = 1, k = 1: 52 % vs 40 %, +12 pts [0, +24] (B). The pooled difference includes 0.
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
| 3 | Main failure stage: B, the filter | The filter drops 0 of the failures (stage B: 0; S). Failures are labelled stage A (36–49 of 75), but the old fact is not a candidate either in 66 of 75, so that is the normal route, not a failure stage (U, §2) | **Miss** |
| 4 | As n grows, HippoRAG's correction@5 drops slower than dense's | It drops faster: −11.7 pts vs −0.7 pts; interaction −11.0 pts [−16.7, −6.0] (U, §1) | **Miss** (opposite direction) |
| 5a | The fix raises correction@5 by +1–5 pts | +0.0 in 7 of 8 cells, +1.3 pts at n = 3, k = 5; pooled +0.2 pts [0.0, +0.5] (B, P) | **Miss** (below the range) |
| 5b | Unchanged-fact Recall@5 changes by about 0 | At k = 0 the fix never fires and the top 5 is identical in 75/75 questions. With k ≥ 1, recall of the other gold passages changes in 1 record at (1,1) and 1 at (1,2): 0.700 → 0.687. No non-target fact was dropped (P, "Fix vs no fix"; S, collateral table) | **Hit** |
| 6 | Account is wrong if the filter keeps > 80 %, or the fix adds > 10 pts | The filter keeps 89 % of the corrections it sees (8/9; per-question CI 67–100 %, 9 questions). The fix adds +0.2 pts (P) | **First falsifier triggered.** The account "the filter is the bottleneck" is wrong |
| 7 | When the model knows o, the filter keeps the correction less often | Knows o: 5 of 6 kept. Does not know: 3 of 3 kept (P). The one dropped correction is a "knows" question, and it is one of the 8 specialist rows (M: 7/7 kept without them) | **Untestable** at 9 questions; direction matches, by one question |
| 8 | Rare vs common o′: untested | Still untested: the ≥ 10 bin has 9 swaps (S, header) | As stated |

Score: 1 hit (5b), 5 misses (1, 2, 3, 4, 5a), 1 untestable (7), 1 untested (8), and the prediction's own falsifier fired (6).

## 3. Attribution

**Revised after the follow-up (U, §2; exploratory, not in the prediction).** The first version of this section said every failure is "seed-slot exclusion at stage A". The counts are right, but the reading was wrong: not being a candidate is the normal state of the last-hop fact, for old facts as much as for corrections.

- **Baseline.** With no correction in the index (k = 0), the old fact is among the 5 candidate facts for 9 of 75 questions, at n = 1 and at n = 3. For corrections the figure is also 9 of 75. These are multi-hop questions; the swapped fact is the last hop and the question text matches first-hop facts.
- **Passages are retrieved without their fact.** At k = 0, n = 1 the old passage is in HippoRAG 2's top 5 for 43 of 75 questions: 9 of the 9 whose fact is a candidate, and 34 of the 66 whose fact is not (52 %). Dense retrieves it for 27 of 75.
- **So stage A is a route, not a failure.** A passage reaches the top 5 either through its fact being seeded (always works: 9 of 9, and 71 of 72 correction records) or through its own passage seed plus graph spread from other seeds (works about half the time at n = 1).

**How corrections reach the top 5** (U, §2, "Route"). Across the 8 cells with k ≥ 1 there are 249 records with a correction in the top 5:

| Route | Records | Share |
|---|---|---|
| The correction's fact was a candidate | 71 | 29 % |
| Not a candidate; the passage is also in the dense top 5, so its own seed (0.05 × dense similarity) is enough | 114 | 46 % |
| Not a candidate; the passage is outside the dense top 5, so it was lifted by graph spread from other seeds | 64 | 26 % |

For the 178 non-candidate records, the passage's own seed arriving directly (no walk) is a median 68 % of its PageRank score (71 % when it is in the dense top 5, 62 % when not). The subject entity was seeded through some other kept fact in 82 of the 178; the object o′ in 8.

**First-failure counts, for the record** (S): A 36, 37, 42, 43 (n = 1; k = 1, 2, 3, 5) and 48, 47, 48, 49 (n = 3) of 75; B 0; C 0; D 1 (n = 3, k = 5, tolerance 0); E 0. Read these as "the passage was not retrieved and its fact was not seeded", which is true of most retrieved passages too.

**What stale copies do** (U, §3; exploratory). 35 records from 18 questions are retrieved at n = 1 and lost at n = 3.

- The old passage outranks the correction in 27 of 35. An old passage is in the top 5 in 19, and in all 19 the correction sits at rank 6–10: it is crowded out by copies of the old passage.
- The old-vs-new order follows dense similarity, not graph structure. The PPR margin correlates with the dense-cosine margin at ρ = +0.91 (n = 35) and has the same sign in 34 of 35. It does not track degree(o) − degree(o′): ρ = +0.14 (p = 0.43), and the sign matches in 12 of 33.
- Whether o′ already exists in the corpus does not explain the penalty: −8.1 pts [−14.4, −3.1] when o′ is absent (N = 40) and −15.7 pts [−25.0, −7.1] when present (N = 35); the difference, +7.6 pts [−2.6, +18.2], includes 0. Dense changes by −0.6 and −0.7.
- Caveat: the 35 records are not independent (18 questions), so the p-values are optimistic.

Of the three mechanisms in the theory, the records point to **top-5 crowding by old copies**, with the order among copies set by passage similarity. They do not support graph asymmetry through the object nodes. Why the same crowding does not cost dense anything is not answered by these records.

## 4. What the seed-stage fix changes

The fix drops the older of two kept facts that share subject and relation.

- It fires for 7 questions, in every k ≥ 1 cell: exactly the ones where both facts survive the filter (P, "Fix vs no fix").
- Where it fires it does what it should at the seed level: the old object loses its seed in 7 of 7, and the correction outranks the old passage in 7 of 7 (before the fix: 2 of 7 at n = 1, k = 1) (P).
- That does not change correction@5, because in those 7 questions the correction was already in the top 5 (7 → 7). The one gain is at n = 3, k = 5 (6 → 7) (P).
- It does remove stale passages from the top 5 when there are many corrections: contamination@5 at n = 3, k = 5 falls from 0.61 to 0.41, −0.20 [−0.40, −0.04]; at n = 1, k = 5 from 0.20 to 0.13, −0.07 [−0.13, −0.01]; no change at k = 1 (B).
- No collateral: 0 non-target facts dropped (S).

In short: the fix is correct but acts at the seed stage, and corrections mostly arrive another way. Of the 249 corrections retrieved across the grid, 178 never had their fact among the candidates (U, §2), so there was no seed for the fix to change.

## 5. Surprises

1. **The filter is not the bottleneck, and most retrieval does not go through seeded facts at all.** I expected gpt-4o-mini to reject counterfactuals. It kept 8 of the 9 it saw (P). The last-hop fact is a candidate for 9 of 75 questions whether it is old or new (U, §2).
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

- Rerun with a larger `linking_top_k` (10, 20): more last-hop facts would be seeded, so the fix would have more to act on. Whether correction@5 rises is an open question. This needs new filter calls (paid).
- Find out why crowding by old copies costs HippoRAG 2 and not dense: rerun retrieval on the n = 3 cells with the old copies' passage seeds zeroed (offline, no API calls).
- Give passages a date and test whether the reader then prefers the correction.
