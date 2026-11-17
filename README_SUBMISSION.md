# Submission: CS F429 Group 6 (Shashwat Mishra, 2024A1PS1260P)

**What this is.** A reproduction of HippoRAG 2 ("From RAG to Memory: Non-Parametric Continual Learning for Large Language Models", ICML 2025, arXiv 2502.14802) on MuSiQue, plus an extension that tests whether its memory accepts a corrected fact. The reproduction recovers the paper's gap over dense retrieval. The extension injects counterfactual corrections and stale copies, attributes every miss to a retrieval stage, and tests a contradiction-aware seeding fix, under a blind, sha256-sealed protocol.

- Code: https://github.com/shashwat01mishra/HippoRAG, branch `dev`. `src/` and `main.py` are byte-identical to upstream HippoRAG 2 (tag `upstream-base`); all my code is in `experiments/` and `demo/`.
- Commit: the zip was built with `git archive` from the final commit on `dev`. Its full hash is in `COMMIT.txt` at the top of the zip and in the zip's archive comment (`unzip -z`).
- The HippoRAG 2 paper is included as `HippoRAG2_paper.pdf` (arXiv 2502.14802).

## Start here

| File | What it is |
|---|---|
| `report/one_page_report.pdf` | The one-page report (printed copy) |
| `deck/deck.pdf` | Presentation slides; speaker notes with a source for every number in `deck/SPEAKER_NOTES.md` |
| `DEMO_RUNBOOK.md` | The commands shown live, in order, with expected output and fallbacks |
| `RESULTS_BRIEF.md` | All results in plain language, each number with its source file |
| `REPRODUCIBILITY.md` | Clean clone → every number, with the cost of each paid step |
| `CODE_MAP.md` | Every file I added: purpose, functions with line numbers, inputs/outputs, upstream calls |
| `PROGRESS.md` | Session log: every run, decision, cost and the sha256 seal |

## Folder map

| Path | Contents |
|---|---|
| `src/`, `main.py` | Upstream HippoRAG 2, unmodified |
| `experiments/` | Reproduction scripts (`run_subset.py`, `bootstrap_gap.py`, `precision_at5.py`, launch guards), the extension harness (`experiments/extension/`: target selection, injection, grid runner, attribution, the fix in `attrib_rag.py`, `analysis.py`, `phase_b.py`, `followup.py`) and the theory check (`experiments/theory/`) |
| `demo/` | `run_demo.py` (offline replay, optional live rerun), saved traces for Q193 and Q96, `graph_stats.md` |
| `results/musique_n500/` | Per-query outputs of the n = 500 reproduction runs, bootstrap CIs, precision@5 |
| `results/extension/grid_v5_20261109/` | The sealed grid records (25 `.jsonl` files) and `SEAL.sha256` |
| `analysis/grid_v5_final/` | Analysis of the 75 final swaps: tables, CSVs, figures, `phase_b.md`, `followup.md` |
| `analysis/grid_v5_final_minus_specialist/` | Sensitivity analysis without 8 borderline swaps |
| `experiments/extension/data/` | Targets (v1–v5), the hand-review file with a reason per swap, `targets_final.jsonl` |
| `notes/` | `prediction.md` (committed blind), `paper_todo.md`, `code-map.md` (upstream code) |
| `deck/`, `report/` | Slides and one-page report, with sources and build scripts |
| `paper/` | IEEE paper draft (results-independent parts) and figures |
| `VIVA.md`, `VIVA_ANSWERS.md`, `ONE_PAGER_FACTS.md` | Viva preparation and the fact list for the report |
| `reproduce/dataset/` | MuSiQue questions and corpus as shipped by upstream |
| `outputs/musique/` | Upstream's released OpenIE extractions (tracked by upstream) |
| `env/requirements-lock.txt` | Exact package versions |

## How to reproduce each number

Follow `REPRODUCIBILITY.md`. In short:

- **No API key needed.** Reproduction CIs (`experiments/bootstrap_gap.py`), precision@5 (`experiments/precision_at5.py`), every extension number (`experiments/extension/analysis.py`, `phase_b.py`, `followup.py` on `results/extension/grid_v5_20261109/`), deck figures (`deck/make_figs.py`), the theory check (`experiments/theory/verify_margin.py`), and the demo replay. The per-query and grid records are included, so all of this runs offline.
- **Needs an API key (paid).** Re-running retrieval and reading (the n = 100 / 500 runs, the grid, the target generation). Commands and costs are in `REPRODUCIBILITY.md`; LLM caches are not included, so a fresh run pays again.
- Seal check: see `DEMO_RUNBOOK.md` step 4 (the `results/` variant works on this archive).

## Excluded, and why

| Excluded | Why |
|---|---|
| `outputs/` indexes and grid working directories (33 GB as reported by `du`, logical size; APFS clones share blocks) | Too large; rebuildable with the commands in `REPRODUCIBILITY.md` (paid). The upstream OpenIE files in `outputs/musique/` are included because upstream tracks them. |
| `.env` (API key) | Secret. Never committed; checked with `git ls-files` and a search of tracked files and history. |
| LLM caches (`outputs/*/llm_cache/`) and `demo/index/` | Part of `outputs/` or a local clone of it; rebuildable |
| `logs/` | Local run logs, gitignored; their key lines are copied into `PROGRESS.md` |
| `.venv/` | Rebuild from `env/requirements-lock.txt` |
