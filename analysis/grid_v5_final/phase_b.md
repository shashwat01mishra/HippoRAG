# Phase B numbers: final targets

N = 75 swaps (model_knows_o yes 31 / no 44). Source: `results/extension/grid_v5_20261109/*.jsonl` via `experiments/extension/phase_b.py`; full numbers in `phase_b.json`. CIs: 10,000 resamples of targets, seed 0, percentile 95 %.

## Funnel (no-fix arm): is the fact among the top-5 candidates, and does the filter keep it

| n | k | old candidate | new candidate | old kept | new kept | both kept | dense fallback | corr@5 if new is a candidate | corr@5 if not | dense corr@5 on those |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 9 | 0 | 9 | 0 | 0 | 2 | - | - | - |
| 1 | 1 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 30/66 (45%) | 22/66 (33%) |
| 1 | 2 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 29/66 (44%) | 21/66 (32%) |
| 1 | 3 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 24/66 (36%) | 21/66 (32%) |
| 1 | 5 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 23/66 (35%) | 22/66 (33%) |
| 3 | 0 | 9 | 0 | 9 | 0 | 0 | 2 | - | - | - |
| 3 | 1 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 18/66 (27%) | 20/66 (30%) |
| 3 | 2 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 19/66 (29%) | 21/66 (32%) |
| 3 | 3 | 8 | 9 | 8 | 8 | 7 | 2 | 9/9 (100%) | 18/66 (27%) | 21/66 (32%) |
| 3 | 5 | 8 | 9 | 8 | 8 | 7 | 2 | 8/9 (89%) | 17/66 (26%) | 22/66 (33%) |

## Filter keep rate for the correction

| n | k | kept, given candidate | kept, of all questions | old kept, given candidate | given candidate, model knows o | given candidate, does not know o |
|---|---|---|---|---|---|---|
| 1 | 1 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 1 | 2 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 1 | 3 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 1 | 5 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 3 | 1 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 3 | 2 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 3 | 3 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |
| 3 | 5 | 8/9 (89%) | 8/75 (11%) | 8/8 (100%) | 5/6 (83%) | 3/3 (100%) |

Pooled over the 8 k ≥ 1 cells, given the correction was a candidate: all 64/72 (89%) of records, per-target mean 89% [67%, 100%] over 9 targets; knows_yes 40/48 (83%) of records, per-target mean 83% [50%, 100%] over 6 targets; knows_no 24/24 (100%) of records, per-target mean 100% [100%, 100%] over 3 targets.

## Records where the filter kept both the old and the new fact (k ≥ 1, no-fix)

56 records from 7 targets. correction@5 55/56 (98%); o′ seeded 56/56 (100%). Median relative PPR margin |new − old| / max: 0.0441. Sign of the PPR margin equals the sign of the dense-cosine margin in 20/56 (36%) (all k ≥ 1 records: 524/600 (87%)).

| tolerance | outranks | near tie | loses |
|---|---|---|---|
| 0 | 23 | 0 | 33 |
| 0.005 | 22 | 1 | 33 |
| 0.01 | 22 | 9 | 25 |
| 0.02 | 21 | 14 | 21 |

## Effect of stale copies: correction@5 change from n = 1 to n = 3 (points)

| k | HippoRAG 2 | dense | HippoRAG 2 − dense |
|---|---|---|---|
| 1 | -16.0 [-25.3, -8.0] | -2.7 [-6.7, +0.0] | -13.3 [-22.7, -4.0] |
| 2 | -13.3 [-21.3, -6.7] | +0.0 [+0.0, +0.0] | -13.3 [-21.3, -6.7] |
| 3 | -8.0 [-14.7, -2.7] | +0.0 [+0.0, +0.0] | -8.0 [-14.7, -2.7] |
| 5 | -9.3 [-16.0, -4.0] | +0.0 [+0.0, +0.0] | -9.3 [-16.0, -4.0] |
| pooled | -11.7 [-17.0, -6.7] | -0.7 [-1.7, +0.0] | -11.0 [-16.7, -6.0] |

## Pooled correction@5 (mean over cells per target, then over targets; %)

| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense (points) | fix − HippoRAG 2 (points) |
|---|---|---|---|---|---|
| all_k>=1_cells | 39.0 [28.3, 49.7] | 41.5 [31.3, 51.5] | 41.7 [31.5, 51.8] | +2.5 [-6.7, +11.3] | +0.2 [+0.0, +0.5] |
| n=1 | 39.3 [28.7, 50.0] | 47.3 [36.7, 58.0] | 47.3 [36.7, 58.0] | +8.0 [-2.0, +18.0] | +0.0 [+0.0, +0.0] |
| n=3 | 38.7 [28.0, 49.3] | 35.7 [25.7, 46.0] | 36.0 [26.0, 46.3] | -3.0 [-12.0, +5.7] | +0.3 [+0.0, +1.0] |

## Pooled contamination@5 (mean number of old passages in the top 5)

| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense | fix − HippoRAG 2 |
|---|---|---|---|---|---|
| k=0 | 0.67 [0.47, 0.87] | 1.00 [0.79, 1.21] | 1.00 [0.79, 1.21] | +0.33 [+0.13, +0.52] | +0.00 [+0.00, +0.00] |
| k>=1 | 0.51 [0.34, 0.68] | 0.62 [0.45, 0.80] | 0.58 [0.42, 0.73] | +0.11 [-0.03, +0.25] | -0.04 [-0.09, -0.01] |

## Fix vs no fix

Targets where the fix ever fired: 7.

| n | k | fix fired | top 5 identical | corr@5 no fix → fix | where fired: corr@5 | where fired: outranks@0 | where fired: old passages in top 5 | where fired: o seeded | other-gold recall@5 no fix → fix (records changed) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 75/75 | - | - | - | - | - | 0.727 → 0.727 (0) |
| 1 | 1 | 7 | 69/75 | 0.520 → 0.520 | 7 → 7 | 2 → 7 | 7 → 7 | 7 → 0 | 0.700 → 0.687 (1) |
| 1 | 2 | 7 | 69/75 | 0.507 → 0.507 | 7 → 7 | 2 → 7 | 7 → 7 | 7 → 0 | 0.667 → 0.653 (1) |
| 1 | 3 | 7 | 70/75 | 0.440 → 0.440 | 7 → 7 | 2 → 7 | 7 → 7 | 7 → 0 | 0.653 → 0.653 (0) |
| 1 | 5 | 7 | 70/75 | 0.427 → 0.427 | 7 → 7 | 2 → 7 | 5 → 0 | 7 → 0 | 0.627 → 0.627 (0) |
| 3 | 0 | 0 | 75/75 | - | - | - | - | - | 0.667 → 0.667 (0) |
| 3 | 1 | 7 | 74/75 | 0.360 → 0.360 | 7 → 7 | 6 → 7 | 21 → 21 | 7 → 0 | 0.653 → 0.653 (0) |
| 3 | 2 | 7 | 73/75 | 0.373 → 0.373 | 7 → 7 | 5 → 7 | 21 → 20 | 7 → 0 | 0.627 → 0.627 (0) |
| 3 | 3 | 7 | 70/75 | 0.360 → 0.360 | 7 → 7 | 2 → 7 | 19 → 13 | 7 → 0 | 0.627 → 0.627 (0) |
| 3 | 5 | 7 | 70/75 | 0.333 → 0.347 | 6 → 7 | 2 → 7 | 15 → 0 | 7 → 0 | 0.627 → 0.627 (0) |

## HippoRAG 2 correction@5 failures (no-fix arm): where the correction sits

| n | k | failures | new fact not a candidate | best correction at rank 6–10 | 11–50 | > 50 | an old passage in top 5 | old outranks new | new outranks old, still outside | dense also fails | lost vs n = 1 (gained) | of the lost: old outranks new / rank 6–10 / mean old in top 5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 36 | 36 | 9 | 15 | 12 | 2 | 14 | 22 | 30 | - | - |
| 1 | 2 | 37 | 37 | 10 | 15 | 12 | 2 | 12 | 25 | 31 | - | - |
| 1 | 3 | 42 | 42 | 11 | 19 | 12 | 3 | 12 | 30 | 36 | - | - |
| 1 | 5 | 43 | 43 | 8 | 20 | 15 | 1 | 11 | 32 | 37 | - | - |
| 3 | 1 | 48 | 48 | 13 | 22 | 13 | 9 | 34 | 14 | 40 | 12 (0) | 10 / 8 / 1.08 |
| 3 | 2 | 47 | 47 | 12 | 19 | 16 | 5 | 29 | 18 | 39 | 10 (0) | 8 / 4 / 0.70 |
| 3 | 3 | 48 | 48 | 13 | 19 | 16 | 6 | 25 | 23 | 40 | 6 (0) | 4 / 5 / 1.83 |
| 3 | 5 | 50 | 49 | 13 | 19 | 18 | 6 | 23 | 27 | 42 | 7 (0) | 5 / 6 / 1.43 |

## Long-context reader (all of the question's passages plus every injected variant)

| n | k | N | answers o′ | answers o | both | neither | o′ when model knows o | o′ when it does not |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 75 | 7 | 41 | 0 | 27 | 3/31 (10%) | 4/44 (9%) |
| 1 | 5 | 75 | 26 | 19 | 0 | 30 | 10/31 (32%) | 16/44 (36%) |
| 3 | 1 | 75 | 1 | 43 | 0 | 31 | 0/31 (0%) | 1/44 (2%) |
| 3 | 5 | 75 | 16 | 32 | 1 | 26 | 6/31 (19%) | 10/44 (23%) |
