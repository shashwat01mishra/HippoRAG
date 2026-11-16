# One-pager facts (bullets only; sources in brackets)

Sources: R = `results/musique_n500/bootstrap_n500.txt` · S = `analysis/grid_v5_final/summary.md` · B = `analysis/grid_v5_final/bootstrap.csv` · P = `analysis/grid_v5_final/phase_b.md` · M = `analysis/grid_v5_final_minus_specialist/phase_b.md` · T = `paper/sections/reproduction.tex` · G = `demo/graph_stats.md` · L = `PROGRESS.md` · F = `experiments/extension/data/review_reasons.md`. CIs: paired bootstrap, 95 %, 10,000 resamples, seed 0.

## Setup
- Base paper: HippoRAG 2 (ICML 2025, arXiv 2502.14802). Dataset: MuSiQue, 11,656 passages [L]
- Models: gpt-4o-mini (all LLM roles), text-embedding-3-small [L]
- `src/` and `main.py`: 0-line diff vs upstream tag `upstream-base` [L]
- OpenIE: authors' released extractions reused, 0 extraction calls [L]
- Graph: 113,200 nodes (101,544 entity, 11,656 passage), 322,183 edges [G]
- Dense baseline ranks the same passage vectors (sha256-identical copy) [L]

## Reproduction (first 500 questions)
- Recall@5: HippoRAG 2 62.00, dense 56.10, gap +5.90 [+3.73, +8.00] [R]
- F1: 44.93 vs 40.27, gap +4.66 [+1.52, +7.69] [R]
- EM: 30.80 vs 27.60, gap +3.20 [+0.00, +6.40] [R]
- Per question, Recall@5: HippoRAG 2 better 113, dense better 52, tied 335 [R]
- Paper, gpt-4o-mini rows (its App. C, Tables 8–9): Recall@5 74.2 vs 69.7 (+4.5); F1 49.3 vs 46.0 (+3.3) [T]
- Both paper gaps lie inside our intervals [R, T]

## Improvement 1: a theory of where resistance can come from
- Toy graph, shared-subject seed: every old and new passage scores d/((1+d)(n+k)) [L, Session 7]
- Checked with sympy and igraph PRPACK, agreement to 2.2e-16 over 480 random resets [L]
- Three possible sources: no seed for the correction; graph asymmetry; top-5 crowding

## Improvement 2: an update-resistance protocol
- Counterfactual swaps: 120 generated, 75 kept after two screening passes [F]
- Integrity check: 0 of 120 swaps altered anything but o → o′ [F]
- Grid: n ∈ {1, 3} old copies × k ∈ {0, 1, 2, 3, 5} corrections; 2 arms; dense on the same index [L]
- Structural gates per cell: 0 OpenIE chunks, 0 embedding calls, traced ranking equals upstream `retrieve()` [L]
- Blind: results sealed by sha256 on 9 Nov; prediction commit `460c50a`, 16 Nov 18:59 IST; seal matched 26/26 [L]

## Findings
- correction@5, pooled over 8 cells: dense 39.0 %, HippoRAG 2 41.5 %, difference +2.5 pts [−6.7, +11.3] [P]
- n = 1, k = 1: 52 % vs 40 %, +12 pts [0, +24] [B]
- n = 1, k = 5: HippoRAG 2 43 %, dense 40 % [S]
- n = 3: HippoRAG 2 33–37 %, dense 37–40 % [S]
- 1 → 3 old copies: HippoRAG 2 −11.7 pts [−17.0, −6.7]; dense −0.7 pts [−1.7, 0.0] [P]
- Before any correction (k = 0, n = 1) the original passage is in the top 5: HippoRAG 2 0.57, dense 0.36 [S]
- Correction's fact among the 5 candidate facts: 9 of 75 questions [P]
- Filter keeps it: 8 of those 9 [P]
- Failures by first failing stage: "not a candidate" 36–49 of 75 per cell; filter 0; later stages 1 in the whole grid [S]
- Old outranks new when both are seeded: 33 of 56 records at tolerance 0 [P]
- Long-context reader answers the new value in 7, 26, 1, 16 of 75 at (n,k) = (1,1), (1,5), (3,1), (3,5) [P]

## Improvement 3: contradiction-aware seeding (the fix)
- Fires for 7 of 75 questions [P]
- Where it fires: old object loses its seed 7/7; correction outranks old 7/7 [P]
- correction@5: +0.2 pts pooled [0.0, +0.5]; +0.0 in 7 of 8 cells [P, B]
- contamination@5 at n = 3, k = 5: 0.61 → 0.41, −0.20 [−0.40, −0.04] [B]
- Non-target facts dropped: 0 [S]
- Top 5 at k = 0: identical in 75/75 [P]

## Prediction scorecard
- 8 items written blind: 1 hit, 5 misses, 1 untestable, 1 untested; own falsifier fired [`RESULTS_BRIEF.md` §2]
- Predicted bottleneck: the filter. Actual bottleneck: the 5-candidate step before it [S, P]

## Sensitivity
- Without the 8 specialist-knowledge swaps (N = 67): 38.4 % vs 39.2 %, −0.7 pts [−9.9, +8.6]; stale-copy change −11.2 pts vs −0.7; fix +0.0 [M]

## Limits
- Filter and fix findings rest on 9 and 7 questions [P]
- No dates on passages; injected copies are exact duplicates apart from the title line [L]
- Synthetic swaps; oracle contradiction detection; one dataset; one LLM [L]

## Cost
- Reproduction ₹17.41 + ₹36.44 (actual key usage) [L]
- Targets ≈ ₹3.60, grid ≈ ₹33.29, demo ≈ ₹0.03 (estimates, list × 1.1) [L]
