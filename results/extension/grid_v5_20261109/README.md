Blind grid run `grid_v5_20261109` (sealed 2026-11-09 04:16:16 IST). sha256-identical copies of `outputs/extension/grid_v5_20261109/results/*.jsonl`. Hashes are in PROGRESS.md (Session 6, "Blind grid run").

- Code: `b4a64ab` (tree clean; `src/` and `main.py` 0-line diff vs `upstream-base`). Targets: `experiments/extension/data/targets_v5.jsonl` (all 120, before hand review). Vectors: `outputs/extension/grid_v5_20261109/vectors.npz` (not copied; hash in PROGRESS).
- `cell_n{n}_k{k}_g{group}.jsonl`: one record per (target, arm), arms no-fix and fix; 20 files (10 cells × 2 collision groups), 2,400 rows.
- `long_context_n{n}_k{k}.jsonl`: long-context reader at the four corners, 120 rows each.
- `cell_stats.jsonl`: per (cell, group) build stats and structural gate results (no metrics).
- Analyse after the prediction is committed, restricted to the hand-kept targets: `analysis.py --results results/extension/grid_v5_20261109 --targets experiments/extension/data/targets_v5.jsonl --final experiments/extension/data/targets_final.jsonl --out <dir>`.
