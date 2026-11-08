Update-resistance extension harness. All code here; `src/` and `main.py` stay identical to `upstream-base`.

| File | Purpose |
|---|---|
| `common.py` | Paths, base-index location, launch args, BaseConfig captured from `run_subset.py`, prices, string helpers |
| `select_targets.py` | Step 1: offline target selection from MuSiQue + cached OpenIE; writes `data/targets.jsonl` |
| `inject.py` | Step 2: deterministic o→o′ swap, title-line variants, OpenIE-state rows with the stamp's provenance |
| `vectors.py` | Embed-once plan, `VectorTable`, strict `FrozenEmbedder`; the one paid embedding step (`--confirm-paid`) |
| `cell_index.py` | Step 3: `cp -c` clone of the base save dir, shared LLM-cache symlink, OpenIE sentinel, incremental index |
| `attrib_rag.py` | Steps 4–5: `AttributionHippoRAG` (stages A–E, dense arm, metrics) and the fix with a canonicalization hook |
| `long_context.py` | Step 6: long-context reader prompt builder and o / o′ / both / neither scorer |
| `run_cells.py` | Step 7: grid runner (`--dry-run`, `--measure` offline rehearsal, `--confirm-paid`) |
| `tests/test_extension.py` | Offline tests on a synthetic corpus (mock LLM, embedder, OpenIE) |
| `data/targets.jsonl` | 120 selected targets (seed 0) |

Tests: `.venv/bin/python -m pytest experiments/extension/tests -q`

Paid sequence (tomorrow): `vectors.py --confirm-paid` → `run_cells.py --confirm-paid --root ... --vectors ...` (one cell first) → full grid → optional `--long_context`.
