# Reproducibility guide (CS F429: HippoRAG 2 reproduction + update-resistance extension)

This file is the project's own guide. `README.md` is upstream's and is left unchanged. Every number in the paper (`paper/`) can be regenerated with the commands below. Paid steps are marked **(paid)** with their cost, at about 1.1× list price and ₹88/$ (all calls go through the AICredits gateway, `https://api.aicredits.in/v1`).

## 0. Environment

- Machine used: MacBook Pro (Apple Silicon, macOS), APFS. The per-cell clones use `cp -c` (APFS copy-on-write); on other filesystems `cp -c` fails rather than falling back to a full copy.
- Python 3.10.22 (uv-managed). Exact package versions: `env/requirements-lock.txt` (`uv pip freeze`).
- Paper: tectonic 0.17.0 (`brew install tectonic`), IEEEtran class (fetched by tectonic).

```zsh
git clone https://github.com/shashwat01mishra/HippoRAG.git nlp-hipporag && cd nlp-hipporag
git checkout dev                    # main stays identical to upstream; work is on dev
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python -r env/requirements-lock.txt     # includes `-e .`
.venv/bin/python -m pytest tests -q --ignore=tests/integration            # 93 upstream tests
.venv/bin/python -m pytest experiments -q                                 # extension + theory tests
printf 'OPENAI_API_KEY=\n' > .env && chmod 600 .env                       # fill in the gateway key
```

Code identity: `src/` and `main.py` must stay byte-identical to tag `upstream-base` (`git diff --stat upstream-base -- src main.py` prints nothing). Every launcher records the commit and this diff in its log.

## 1. Data provenance

| Item | Source | Notes |
|---|---|---|
| `reproduce/dataset/musique.json` (1,000 questions), `musique_corpus.json` (11,656 passages) | shipped in git by upstream; sha256-identical to the HF dataset `osunlp/HippoRAG_2` | evaluation uses the first N questions in file order |
| `outputs/musique/openie_results_ner_gpt-4o-mini.json` | upstream release (gpt-4o-mini OpenIE extractions) | has no provenance block; stamped by `experiments/stamp_openie_cache.py` (the stamp asserts the extractions match the current prompt, which cannot be verified) |
| `experiments/extension/data/targets_v5.jsonl` | built by `select_targets_v4.py` (generation) + `select_targets_v5.py` (checks, probe) + `reprobe_v5.py` | LLM caches under `outputs/extension/target_*`, `knowledge_probe_*` replay every call for free |
| `experiments/extension/data/targets_final.jsonl` | `finalize_targets.py` from the hand marks in `review_v5.md` | not yet written (hand review pending) |
| `results/musique_n500/`, `results/extension/grid_v5_20261109/` | sha256-identical copies of run outputs | hashes in `PROGRESS.md` |

## 2. Reproduction (HippoRAG 2 vs dense on MuSiQue)

```zsh
# OpenIE stamp for the run's save dir (offline)
.venv/bin/python experiments/stamp_openie_cache.py --save_dir outputs/hipporag_n100_musique \
    --llm_name gpt-4o-mini --llm_base_url https://api.aicredits.in/v1
ARGS=(--dataset musique --llm_base_url https://api.aicredits.in/v1 --llm_name gpt-4o-mini
      --embedding_name text-embedding-3-small --embedding_base_url https://api.aicredits.in/v1 --embedding_batch_size 128)
# (paid, ₹17.4 actual, incl. the full-corpus embedding pass) HippoRAG 2, first 100 questions; launcher checks tree, logs, OpenIE guard
tmux new -s n100 "zsh experiments/launch_run.zsh hipporag_n100 --rag_type hipporag --num_queries 100 $ARGS --save_dir outputs/hipporag_n100"
# dense baseline ranks with HippoRAG's own passage vectors (offline copy), then (paid) runs
.venv/bin/python experiments/share_chunks_to_dense.py
tmux new -s d100 "zsh experiments/launch_run.zsh dense_n100 --rag_type standard --num_queries 100 $ARGS --save_dir outputs/dense_n100"
# n = 500: copy the n = 100 save dirs (index + llm_cache) to outputs/{hipporag,dense}_n500_musique, then (paid, ₹36.4 actual for both)
tmux new -s n500 "zsh experiments/launch_run.zsh hipporag_n500 --rag_type hipporag --num_queries 500 $ARGS --save_dir outputs/hipporag_n500"
tmux new -s d500 "zsh experiments/launch_run.zsh dense_n500 --rag_type standard --num_queries 500 $ARGS --save_dir outputs/dense_n500"
# paired bootstrap CIs (offline)
.venv/bin/python experiments/bootstrap_gap.py --hipporag outputs/hipporag_n500_musique/per_query_n500.json \
    --dense outputs/dense_n500_musique/per_query_n500.json
.venv/bin/python experiments/bootstrap_gap.py --hipporag outputs/hipporag_n500_musique/per_query_n500.json \
    --dense outputs/dense_n500_musique/per_query_n500.json --first 100
```

Expected (paper Table II and Fig. 3): N = 500 Recall@5 62.00 vs 56.10, F1 44.93 vs 40.27; gaps +5.90 [+3.73, +8.00] and +4.66 [+1.52, +7.69]. Answer-level reruns are not bit-identical (query embeddings are re-fetched).

## 3. Theory (offline)

```zsh
.venv/bin/python experiments/theory/verify_margin.py      # sympy derivation + igraph PRPACK check; exit 0 iff all pass
```

## 4. Extension (update resistance)

Targets (all calls cached; a rerun from the caches is free; costs are for a fresh run):

| Step | Command | Cost |
|---|---|---|
| anchors, generation of o′ (paid) | `select_targets_v4.py --confirm-paid` | ₹0.98 |
| truth-blind checks + bare probe (paid) | `select_targets_v5.py --confirm-paid` | ₹0.75 |
| title-disambiguated probe (paid) | `reprobe_v5.py --confirm-paid` | ₹0.16 |
| hand review → final set (offline) | edit `review_v5.md`, then `finalize_targets.py` | — |

The superseded v2/v3 pickers (`select_targets_v2.py`, `select_targets_v3.py`; ₹1.40 and ₹0.31) are kept for the record; v5 doesn't depend on them.

Grid (`RUN=grid_v5_20261109`, `T=experiments/extension/data/targets_v5.jsonl`):

```zsh
.venv/bin/python experiments/extension/run_cells.py --dry-run --targets $T                      # costs, disk, time (offline)
.venv/bin/python experiments/extension/run_cells.py --measure <scratch dir> --targets $T --cells 1,1   # offline gate rehearsal
.venv/bin/python experiments/extension/vectors.py --targets $T --out outputs/extension/$RUN/vectors.npz --confirm-paid   # (paid) ₹0.22
.venv/bin/python experiments/extension/run_cells.py --confirm-paid --run_id $RUN --targets $T \
    --vectors outputs/extension/$RUN/vectors.npz --cells 1,1                                     # (paid) filter calls
.venv/bin/python experiments/extension/run_cells.py --confirm-paid --run_id $RUN --targets $T \
    --vectors outputs/extension/$RUN/vectors.npz --cells 1,0 1,2 1,3 1,5 3,0 3,1 3,2 3,3 3,5     # (paid) filter calls
.venv/bin/python experiments/extension/run_cells.py --confirm-paid --run_id $RUN --targets $T --long_context   # (paid) ₹27.09
```

- **Filter-call cost.** The two cell steps are bounded by the dry-run estimate (≤ 2 filter calls per question; ≈ ₹10.6 at 120 targets). The actual cost is recorded in `PROGRESS.md`, but it depends on LLM-cache hits, which depend on retrieval behaviour, so it is withheld here until the analysis is unsealed.
- **Gates.** Every (cell, group) run checks, structurally:
  - 0 OpenIE chunks;
  - 0 embedding calls;
  - all injected passages present;
  - identical filter prompts across the fix and no-fix arms;
  - 5 traced rankings equal upstream `retrieve()`.
  A failing gate aborts the run.
- **Seal.** The sha256 of every results file is in `PROGRESS.md` (2026-11-09 04:16:16 IST, commit `c68a13e`). Check with `shasum -a 256 results/extension/grid_v5_20261109/*.jsonl`.

Analysis (offline; only after the prediction is committed):

```zsh
.venv/bin/python experiments/extension/analysis.py --results results/extension/grid_v5_20261109 \
    --targets experiments/extension/data/targets_v5.jsonl --final experiments/extension/data/targets_final.jsonl \
    --out analysis/grid_v5 --tex_dir paper/tables
.venv/bin/python experiments/extension/analysis.py --results results/extension/grid_v5_20261109 \
    --targets experiments/extension/data/targets_v5.jsonl --trace --cell 1,1 --n_trace 3
```

## 5. Paper and figures

```zsh
.venv/bin/python paper/figs/make_figures.py                 # pipeline, toy graph, reproduction gap (PDF + 2x PNG)
cd paper && tectonic -X compile main.tex                    # result tables/figures appear once paper/tables and paper/figs/results exist
```
