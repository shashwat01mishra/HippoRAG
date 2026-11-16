# Phase B numbers: final targets minus review rows 19,25,29,45,91,100,109,114

N = 67 swaps (model_knows_o yes 27 / no 40). Source: `results/extension/grid_v5_20261109/*.jsonl` via `experiments/extension/phase_b.py`; full numbers in `phase_b.json`. CIs: 10,000 resamples of targets, seed 0, percentile 95 %.

## Funnel (no-fix arm): is the fact among the top-5 candidates, and does the filter keep it

| n | k | old candidate | new candidate | old kept | new kept | both kept | dense fallback | corr@5 if new is a candidate | corr@5 if not | dense corr@5 on those |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 7 | 0 | 7 | 0 | 0 | 2 | - | - | - |
| 1 | 1 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 25/60 (42%) | 20/60 (33%) |
| 1 | 2 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 24/60 (40%) | 19/60 (32%) |
| 1 | 3 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 21/60 (35%) | 19/60 (32%) |
| 1 | 5 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 20/60 (33%) | 20/60 (33%) |
| 3 | 0 | 7 | 0 | 7 | 0 | 0 | 2 | - | - | - |
| 3 | 1 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 15/60 (25%) | 18/60 (30%) |
| 3 | 2 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 16/60 (27%) | 19/60 (32%) |
| 3 | 3 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 15/60 (25%) | 19/60 (32%) |
| 3 | 5 | 6 | 7 | 6 | 7 | 6 | 2 | 7/7 (100%) | 14/60 (23%) | 20/60 (33%) |

## Filter keep rate for the correction

| n | k | kept, given candidate | kept, of all questions | old kept, given candidate | given candidate, model knows o | given candidate, does not know o |
|---|---|---|---|---|---|---|
| 1 | 1 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 1 | 2 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 1 | 3 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 1 | 5 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 3 | 1 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 3 | 2 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 3 | 3 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |
| 3 | 5 | 7/7 (100%) | 7/67 (10%) | 6/6 (100%) | 4/4 (100%) | 3/3 (100%) |

Pooled over the 8 k ≥ 1 cells, given the correction was a candidate: all 56/56 (100%) of records, per-target mean 100% [100%, 100%] over 7 targets; knows_yes 32/32 (100%) of records, per-target mean 100% [100%, 100%] over 4 targets; knows_no 24/24 (100%) of records, per-target mean 100% [100%, 100%] over 3 targets.

## Records where the filter kept both the old and the new fact (k ≥ 1, no-fix)

48 records from 6 targets. correction@5 48/48 (100%); o′ seeded 48/48 (100%). Median relative PPR margin |new − old| / max: 0.0639. Sign of the PPR margin equals the sign of the dense-cosine margin in 20/48 (42%) (all k ≥ 1 records: 485/536 (90%)).

| tolerance | outranks | near tie | loses |
|---|---|---|---|
| 0 | 23 | 0 | 25 |
| 0.005 | 22 | 1 | 25 |
| 0.01 | 22 | 3 | 23 |
| 0.02 | 21 | 6 | 21 |

## Effect of stale copies: correction@5 change from n = 1 to n = 3 (points)

| k | HippoRAG 2 | dense | HippoRAG 2 − dense |
|---|---|---|---|
| 1 | -14.9 [-23.9, -7.5] | -3.0 [-7.5, +0.0] | -11.9 [-22.4, -3.0] |
| 2 | -11.9 [-19.4, -4.5] | +0.0 [+0.0, +0.0] | -11.9 [-19.4, -4.5] |
| 3 | -9.0 [-16.4, -3.0] | +0.0 [+0.0, +0.0] | -9.0 [-16.4, -3.0] |
| 5 | -9.0 [-16.4, -3.0] | +0.0 [+0.0, +0.0] | -9.0 [-16.4, -3.0] |
| pooled | -11.2 [-17.2, -6.0] | -0.7 [-1.9, +0.0] | -10.4 [-16.4, -5.2] |

## Pooled correction@5 (mean over cells per target, then over targets; %)

| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense (points) | fix − HippoRAG 2 (points) |
|---|---|---|---|---|---|
| all_k>=1_cells | 39.2 [28.0, 50.7] | 38.4 [28.2, 49.1] | 38.4 [28.2, 49.1] | -0.7 [-9.9, +8.6] | +0.0 [+0.0, +0.0] |
| n=1 | 39.6 [28.4, 51.1] | 44.0 [33.2, 55.2] | 44.0 [33.2, 55.2] | +4.5 [-6.0, +14.9] | +0.0 [+0.0, +0.0] |
| n=3 | 38.8 [27.6, 50.4] | 32.8 [22.8, 43.7] | 32.8 [22.8, 43.7] | -6.0 [-14.9, +3.0] | +0.0 [+0.0, +0.0] |

## Pooled contamination@5 (mean number of old passages in the top 5)

| cells | dense | HippoRAG 2 | + fix | HippoRAG 2 − dense | fix − HippoRAG 2 |
|---|---|---|---|---|---|
| k=0 | 0.67 [0.46, 0.90] | 0.92 [0.70, 1.14] | 0.92 [0.70, 1.14] | +0.25 [+0.06, +0.45] | +0.00 [+0.00, +0.00] |
| k>=1 | 0.50 [0.33, 0.69] | 0.57 [0.40, 0.75] | 0.52 [0.37, 0.69] | +0.06 [-0.07, +0.20] | -0.04 [-0.09, -0.01] |

## Fix vs no fix

Targets where the fix ever fired: 6.

| n | k | fix fired | top 5 identical | corr@5 no fix → fix | where fired: corr@5 | where fired: outranks@0 | where fired: old passages in top 5 | where fired: o seeded | other-gold recall@5 no fix → fix (records changed) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 67/67 | - | - | - | - | - | 0.724 → 0.724 (0) |
| 1 | 1 | 6 | 62/67 | 0.478 → 0.478 | 6 → 6 | 2 → 6 | 6 → 6 | 6 → 0 | 0.694 → 0.679 (1) |
| 1 | 2 | 6 | 62/67 | 0.463 → 0.463 | 6 → 6 | 2 → 6 | 6 → 6 | 6 → 0 | 0.664 → 0.649 (1) |
| 1 | 3 | 6 | 63/67 | 0.418 → 0.418 | 6 → 6 | 2 → 6 | 6 → 6 | 6 → 0 | 0.649 → 0.649 (0) |
| 1 | 5 | 6 | 63/67 | 0.403 → 0.403 | 6 → 6 | 2 → 6 | 4 → 0 | 6 → 0 | 0.619 → 0.619 (0) |
| 3 | 0 | 0 | 67/67 | - | - | - | - | - | 0.664 → 0.664 (0) |
| 3 | 1 | 6 | 67/67 | 0.328 → 0.328 | 6 → 6 | 6 → 6 | 18 → 18 | 6 → 0 | 0.649 → 0.649 (0) |
| 3 | 2 | 6 | 66/67 | 0.343 → 0.343 | 6 → 6 | 5 → 6 | 18 → 17 | 6 → 0 | 0.619 → 0.619 (0) |
| 3 | 3 | 6 | 63/67 | 0.328 → 0.328 | 6 → 6 | 2 → 6 | 16 → 11 | 6 → 0 | 0.619 → 0.619 (0) |
| 3 | 5 | 6 | 63/67 | 0.313 → 0.313 | 6 → 6 | 2 → 6 | 12 → 0 | 6 → 0 | 0.619 → 0.619 (0) |

## HippoRAG 2 correction@5 failures (no-fix arm): where the correction sits

| n | k | failures | new fact not a candidate | best correction at rank 6–10 | 11–50 | > 50 | an old passage in top 5 | old outranks new | new outranks old, still outside | dense also fails | lost vs n = 1 (gained) | of the lost: old outranks new / rank 6–10 / mean old in top 5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 35 | 35 | 9 | 15 | 11 | 2 | 14 | 21 | 29 | - | - |
| 1 | 2 | 36 | 36 | 10 | 15 | 11 | 2 | 12 | 24 | 30 | - | - |
| 1 | 3 | 39 | 39 | 9 | 19 | 11 | 2 | 11 | 28 | 33 | - | - |
| 1 | 5 | 40 | 40 | 8 | 18 | 14 | 1 | 10 | 30 | 34 | - | - |
| 3 | 1 | 45 | 45 | 12 | 21 | 12 | 8 | 32 | 13 | 37 | 10 (0) | 8 / 7 / 1.20 |
| 3 | 2 | 44 | 44 | 12 | 17 | 15 | 5 | 27 | 17 | 36 | 8 (0) | 6 / 4 / 0.88 |
| 3 | 3 | 45 | 45 | 13 | 17 | 15 | 6 | 23 | 22 | 37 | 6 (0) | 4 / 5 / 1.83 |
| 3 | 5 | 46 | 46 | 12 | 18 | 16 | 5 | 20 | 26 | 38 | 6 (0) | 4 / 5 / 1.17 |

## Long-context reader (all of the question's passages plus every injected variant)

| n | k | N | answers o′ | answers o | both | neither | o′ when model knows o | o′ when it does not |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 67 | 4 | 38 | 0 | 25 | 1/27 (4%) | 3/40 (8%) |
| 1 | 5 | 67 | 23 | 17 | 0 | 27 | 8/27 (30%) | 15/40 (38%) |
| 3 | 1 | 67 | 1 | 38 | 0 | 28 | 0/27 (0%) | 1/40 (2%) |
| 3 | 5 | 67 | 14 | 29 | 1 | 23 | 4/27 (15%) | 10/40 (25%) |
