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
| `select_targets_v2.py` | Targets v2: same anchors/strata/collision rules; o′ picked by gpt-4o-mini from ≤8 same-relation candidates (paid, ~₹1.1) |
| `run_cells.py` | Step 7: grid runner (`--dry-run`, `--measure` offline rehearsal of every cell, `--confirm-paid` into `outputs/extension/<run_id>/`) |
| `analysis.py` | Metrics by (n, k) × stratum × arm, tolerance sweep, first-failure attribution, PNG figures, `--trace` printer |
| `tests/test_extension.py` | Offline tests on a synthetic corpus (mock LLM, embedder, OpenIE) |
| `data/targets.jsonl` | v1: 120 targets, o′ drawn at random from same-relation objects (seed 0). Superseded by `targets_v2.jsonl` |

Tests: `.venv/bin/python -m pytest experiments/extension/tests -q`. Figures need matplotlib (installed in `.venv`; not in the upstream requirements).

## Method notes

- **Contradiction detection is an oracle.** The fix treats two kept facts as contradicting when their normalized (subject, relation) strings match exactly and their objects differ (`canonical_fact_key` in `attrib_rag.py`). In this protocol the corrected passage is the gold passage with o→o′ swapped, so the correction's triple has exactly the old triple's subject and relation: exact match always detects the injected contradiction (oracle recall). The fix therefore measures *resolution under perfect detection*; detection quality (relation paraphrase, entity aliasing) is out of scope. One known false-positive path remains: a multi-valued relation (e.g. *befriended X*, *befriended Y*) where an injected variant re-asserts one value makes the other look older, and the fix drops it. The records log every dropped fact (`fix_trace.dropped`), so these cases are countable.
- **o′ (v2) is chosen by gpt-4o-mini**; the triples are still copied from the OpenIE cache with o replaced, never extracted.
- **Tolerance at analysis time.** Records keep raw best-new / best-old scores (PPR for HippoRAG, raw cosine for dense). `analysis.py` reports outranks / near-tie / loses at 0, 0.5 %, 1 % and 2 % relative tolerance.
- **Attribution** (HippoRAG arms, k ≥ 1, correction@5 failures): the first stage that fails, A (new fact not a candidate) → B (filter dropped it) → C (o′ not seeded) → D (margin favours old beyond the tolerance) → E (outranks or ties old but outside the top 5). Order and predicates are configurable (`STAGE_ORDER`, `STAGE_RULES`).

## Paid sequence (each step only after an explicit OK, and only after the prediction is committed)

1. `select_targets_v2.py --confirm-paid` → `data/targets_v2.jsonl` (~₹1.1).
2. `vectors.py --targets data/targets_v2.jsonl --out outputs/extension/<run_id>/vectors.npz --confirm-paid` (embed once).
3. `run_cells.py --confirm-paid --run_id <run_id> --vectors ... --cells 1,1`, then `analysis.py --trace --cell 1,1`.
4. The other 9 cells (fix arm included; it re-uses the cached filter prompts).
5. `run_cells.py --confirm-paid --run_id <run_id> --long_context` (four corners by default).
