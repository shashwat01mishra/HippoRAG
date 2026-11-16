# Follow-up analyses (existing records only)

N = 75 swaps. Source: `results/extension/grid_v5_20261109/*.jsonl` and, for node degrees, the cell graphs under `outputs/extension/grid_v5_20261109/`, via `experiments/extension/followup.py`; full numbers in `followup.json`. CIs: 10,000 resamples of targets, seed 0, percentile 95 %.

## 1. Interaction: is the graph more repetition-sensitive than dense? (tests prediction item 4)

Change in correction@5 from n = 1 to n = 3, in points; interaction = HippoRAG 2 change − dense change.

| k | HippoRAG 2 | dense | interaction |
|---|---|---|---|
| 1 | -16.0 [-25.3, -8.0] | -2.7 [-6.7, +0.0] | -13.3 [-22.7, -4.0] |
| 2 | -13.3 [-21.3, -6.7] | +0.0 [+0.0, +0.0] | -13.3 [-21.3, -6.7] |
| 3 | -8.0 [-14.7, -2.7] | +0.0 [+0.0, +0.0] | -8.0 [-14.7, -2.7] |
| 5 | -9.3 [-16.0, -4.0] | +0.0 [+0.0, +0.0] | -9.3 [-16.0, -4.0] |
| pooled over k | -11.7 [-17.0, -6.7] | -0.7 [-1.7, +0.0] | **-11.0 [-16.7, -6.0]** |

Per question (pooled over k): HippoRAG 2 is worse at n = 3 for 18 questions and better for 0; dense is worse for 2 and better for 0.

## 2. EXPLORATORY: baseline for the old fact, and the route into the top 5

### k = 0 (no correction): the old fact and its passage

| n | old fact among the 5 candidates | old passage in HippoRAG 2 top 5 | ... if the fact is a candidate | ... if it is not | old passage in dense top 5 |
|---|---|---|---|---|---|
| 1 | 9/75 (12%) | 43/75 (57%) | 9/9 (100%) | 34/66 (52%) | 27/75 (36%) |
| 3 | 9/75 (12%) | 40/75 (53%) | 9/9 (100%) | 31/66 (47%) | 28/75 (37%) |

### Route into HippoRAG 2's top 5 when the passage's fact was not a candidate

"Also in dense top 5": the passage seed alone (0.05 × min-max dense) ranks it in the top 5. "Not in dense top 5": it needed graph spread from other seeds. Direct-teleport share = (1 − d) · seed / reset total / PPR score with d = 0.5: the part of the passage's score that is its own seed with no walk.

| cell | in top 5 | fact was a candidate | not a candidate | of those: dense fallback | also in dense top 5 | not in dense top 5 (rank 6–20 / > 20) | direct-teleport share of PPR score, median (in dense top 5 / not) | subject entity seeded | own object seeded |
|---|---|---|---|---|---|---|---|---|---|
| old passage, n = 1, k = 0 | 43 | 9 | 34 | 0 | 17 | 17 (5 / 12) | 34.0% (39.1% / 31.8%) | 17 | 3 |
| old passage, n = 3, k = 0 | 40 | 9 | 31 | 0 | 17 | 14 (5 / 9) | 60.2% (63.1% / 58.1%) | 14 | 3 |
| correction, n = 1, k = 1 | 39 | 9 | 30 | 0 | 16 | 14 (4 / 10) | 50.2% (52.5% / 45.7%) | 15 | 1 |
| correction, n = 1, k = 2 | 38 | 9 | 29 | 0 | 15 | 14 (5 / 9) | 60.9% (62.4% / 56.1%) | 14 | 1 |
| correction, n = 1, k = 3 | 33 | 9 | 24 | 0 | 15 | 9 (5 / 4) | 68.9% (69.3% / 58.6%) | 11 | 1 |
| correction, n = 1, k = 5 | 32 | 9 | 23 | 0 | 16 | 7 (4 / 3) | 75.4% (76.8% / 68.4%) | 10 | 1 |
| correction, n = 3, k = 1 | 27 | 9 | 18 | 0 | 12 | 6 (3 / 3) | 65.6% (69.9% / 56.8%) | 7 | 1 |
| correction, n = 3, k = 2 | 28 | 9 | 19 | 0 | 13 | 6 (3 / 3) | 68.8% (73.6% / 62.2%) | 9 | 1 |
| correction, n = 3, k = 3 | 27 | 9 | 18 | 0 | 13 | 5 (3 / 2) | 71.9% (75.4% / 64.1%) | 9 | 1 |
| correction, n = 3, k = 5 | 25 | 8 | 17 | 0 | 14 | 3 (2 / 1) | 75.7% (78.1% / 69.2%) | 7 | 1 |
| **correction, all 8 cells** | 249 | 71 | 178 | 0 | 114 | 64 (29 / 35) | 67.6% (71.0% / 61.8%) | 82 | 8 |

## 3. EXPLORATORY: asymmetry

### HippoRAG 2's n = 1 → 3 change by whether o′ already exists in the corpus (points, pooled over k)

| o′ | N | correction@5 at n = 1 | at n = 3 | HippoRAG 2 change | dense change |
|---|---|---|---|---|---|
| absent (new node) | 40 | 40.6% | 32.5% | -8.1 [-14.4, -3.1] | -0.6 [-1.9, +0.0] |
| present | 35 | 55.0% | 39.3% | -15.7 [-25.0, -7.1] | -0.7 [-2.1, +0.0] |

Absent minus present: +7.6 [-2.6, +18.2] points.

### Questions HippoRAG 2 retrieves at n = 1 and loses at n = 3

35 records from 18 questions (k = 1, 2, 3, 5). The old passage outranks the correction in 27. o′ is absent from the base corpus in 13. Node degree in the n = 3 cell's graph: degree(o) > degree(o′) in 12, equal in 2, smaller in 21; median difference -2. Among records with unequal degrees, the sign of the PPR margin matches the sign of the degree difference in 12/33 (36%).

- old-minus-new PPR margin vs degree(o) − degree(o′): ρ = +0.14 (p = 0.43, n = 35)
- relative margin vs degree difference: ρ = +0.08 (p = 0.64, n = 35)
- PPR margin vs dense-cosine margin (old − new): ρ = +0.91 (p = 0.00, n = 35)

| question | k | o → o′ | o′ absent | degree o | degree o′ | PPR margin old − new | relative | cosine margin old − new | old in top 5 | best correction rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 2hop__161151_42429 | 1 | 10 February 1763 → 15 March 1763 | yes | 7 | 13 | +2.16e-06 | +1.1% | +0.0035 | 2 | 7 |
| 2hop__161151_42429 | 2 | 10 February 1763 → 15 March 1763 | yes | 7 | 14 | +1.71e-06 | +0.9% | +0.0035 | 2 | 6 |
| 2hop__249867_557232 | 1 | Maricopa County → Pima County | no | 8 | 16 | +6.63e-06 | +5.5% | +0.0145 | 0 | 12 |
| 2hop__249867_557232 | 2 | Maricopa County → Pima County | no | 8 | 17 | +4.88e-06 | +4.3% | +0.0128 | 0 | 18 |
| 2hop__263728_705527 | 1 | Ahmad Shah Bahadur → Bahadur Shah I | yes | 4 | 2 | +9.34e-06 | +5.6% | +0.0338 | 1 | 9 |
| 2hop__263728_705527 | 2 | Ahmad Shah Bahadur → Bahadur Shah I | yes | 4 | 3 | +9.27e-06 | +6.0% | +0.0338 | 0 | 11 |
| 2hop__358582_189042 | 1 | New Renaissance Records → Atlantic Records | no | 4 | 9 | -4.65e-07 | -0.4% | -0.0028 | 0 | 10 |
| 2hop__358582_189042 | 2 | New Renaissance Records → Atlantic Records | no | 4 | 10 | -8.98e-07 | -0.8% | -0.0047 | 0 | 17 |
| 2hop__463884_807572 | 1 | Monmouth County → Burlington County | no | 21 | 21 | +2.37e-06 | +2.0% | +0.0102 | 2 | 6 |
| 2hop__463884_807572 | 2 | Monmouth County → Burlington County | no | 21 | 22 | +2.28e-06 | +2.1% | +0.0102 | 0 | 15 |
| 2hop__463884_807572 | 3 | Monmouth County → Burlington County | no | 21 | 23 | -1.35e-08 | -0.0% | -0.0001 | 0 | 23 |
| 2hop__559076_55984 | 1 | Phil Hanseroth → Tori Amos | no | 4 | 4 | +5.17e-06 | +2.5% | +0.0148 | 3 | 6 |
| 2hop__559076_55984 | 2 | Phil Hanseroth → Tori Amos | no | 4 | 5 | +4.48e-06 | +2.3% | +0.0148 | 3 | 6 |
| 2hop__559076_55984 | 3 | Phil Hanseroth → Tori Amos | no | 4 | 6 | +4.15e-06 | +2.3% | +0.0148 | 3 | 6 |
| 2hop__559076_55984 | 5 | Phil Hanseroth → Tori Amos | no | 4 | 8 | +3.07e-06 | +1.8% | +0.0115 | 3 | 6 |
| 2hop__632234_122868 | 1 | University of British Columbia → Simon Fraser University | yes | 6 | 2 | +2.44e-06 | +2.0% | +0.0169 | 0 | 13 |
| 2hop__632234_122868 | 2 | University of British Columbia → Simon Fraser University | yes | 6 | 3 | +2.40e-06 | +2.1% | +0.0154 | 0 | 21 |
| 2hop__636597_480615 | 3 | Ningbo → Hangzhou | no | 5 | 17 | +2.89e-06 | +2.2% | +0.0051 | 3 | 7 |
| 2hop__636597_480615 | 5 | Ningbo → Hangzhou | no | 5 | 19 | +1.90e-06 | +1.6% | +0.0051 | 1 | 9 |
| 2hop__678516_179720 | 5 | Harold Knight → John Singer Sargent | no | 5 | 9 | -4.93e-07 | -0.5% | -0.0037 | 0 | 14 |
| 2hop__731584_700117 | 1 | Berrien County → Kalamazoo County | yes | 4 | 2 | -9.13e-06 | -7.4% | -0.0419 | 0 | 31 |
| 2hop__781079_9237 | 1 | September 2012 → March 2010 | no | 19 | 23 | +1.58e-06 | +0.7% | +0.0021 | 2 | 6 |
| 2hop__794999_113442 | 5 | 13 August 1896 → 5 July 1900 | yes | 13 | 11 | -5.55e-07 | -0.5% | -0.0002 | 0 | 10 |
| 2hop__829358_754719 | 1 | Minas Gerais → São Paulo | no | 18 | 30 | +6.01e-06 | +5.7% | +0.0176 | 0 | 42 |
| 2hop__829358_754719 | 2 | Minas Gerais → São Paulo | no | 18 | 31 | +3.81e-06 | +4.0% | +0.0115 | 0 | 127 |
| 2hop__96411_159054 | 3 | Robert Ludlum → John Grisham | yes | 16 | 4 | +1.08e-05 | +4.9% | +0.0150 | 3 | 7 |
| 2hop__96411_159054 | 5 | Robert Ludlum → John Grisham | yes | 16 | 6 | +8.56e-06 | +4.2% | +0.0047 | 2 | 7 |
| 3hop1__106845_5188_86687 | 2 | May 1990 → April 1991 | yes | 11 | 25 | +8.76e-07 | +0.5% | +0.0016 | 2 | 6 |
| 3hop1__106845_5188_86687 | 3 | May 1990 → April 1991 | yes | 11 | 26 | +4.65e-07 | +0.2% | +0.0003 | 2 | 6 |
| 3hop1__106845_5188_86687 | 5 | May 1990 → April 1991 | yes | 11 | 28 | +3.08e-07 | +0.2% | +0.0003 | 1 | 7 |
| 3hop1__278222_42197_18397 | 1 | Politburo → Central Committee | no | 9 | 5 | +1.62e-06 | +1.0% | +0.0028 | 2 | 6 |
| 3hop1__423001_503371_21711 | 5 | 15th century → 14th century | no | 31 | 53 | +1.51e-06 | +0.9% | -0.0021 | 3 | 6 |
| 3hop1__9285_5188_63702 | 1 | June 1941 → September 1940 | no | 17 | 14 | +1.17e-06 | +0.6% | +0.0046 | 1 | 7 |
| 3hop1__9285_5188_63702 | 2 | June 1941 → September 1940 | no | 17 | 15 | -4.54e-07 | -0.2% | -0.0015 | 0 | 6 |
| 3hop1__9285_5188_63702 | 3 | June 1941 → September 1940 | no | 17 | 16 | -5.23e-07 | -0.3% | -0.0015 | 0 | 7 |
