# Code map: everything added on top of upstream HippoRAG 2

Scope: every file under `experiments/`, plus `demo/` and `paper/figs/make_figures.py`. `src/` and `main.py` are byte-identical to tag `upstream-base` (`git diff --stat upstream-base -- src main.py` is empty). The upstream code itself is mapped in `notes/code-map.md`.

"Deck" refers to the slide plan for Presentation 2 (slides 1–9 plus backups). The deck is `deck/deck.tex`; each number's source file is in `deck/SPEAKER_NOTES.md`. Line numbers are for commit `14deafc` plus this session's uncommitted `demo/` files; they drift with edits.

Upstream functions are written `HippoRAG.method` and live in `src/hipporag/HippoRAG.py` unless noted.

---

## Reproduction (HippoRAG 2 vs dense on MuSiQue)

### `experiments/run_subset.py` (151 lines)
- **Purpose.** `main.py` with two changes: it takes `--num_queries N` (first N questions in file order), and passes `embedding_base_url` into `BaseConfig`, so the gateway is recorded in the config and index manifest. It also dumps per-query results.
- **Key functions.** `get_gold_docs` :25, `get_gold_answers` :44, `parse_args` :66, `main` :90 (BaseConfig :114–136: `linking_top_k=5`, `qa_top_k=5`, `retrieval_top_k=200`, the Llama-3.3 DSPy filter prompt file).
- **In.** `reproduce/dataset/musique{,_corpus}.json`, the stamped OpenIE state in the save dir.
- **Out.** `<save_dir>/per_query_n<N>.json` (:143–146), the index under `<save_dir>/gpt-4o-mini_text-embedding-3-small/`, and the run log (via `launch_run.zsh`).
- **Calls upstream.** `HippoRAG` / `StandardRAG` constructors, `.index` :140, `.rag_qa` :141; `BaseConfig`; `string_to_bool`.
- **Deck.** Slide 4: Recall@5 62.00 vs 56.10 and F1 44.93 vs 40.27 at n = 500 (`results/musique_n500/`).

### `experiments/launch_run.zsh` (26 lines)
- **Purpose.** The only way paid reproduction runs are launched. It refuses a dirty tree (:14), logs the commit and the `src/`+`main.py` diff vs `upstream-base` (:10–11), runs the OpenIE guard for HippoRAG runs (:16–20), then runs `run_subset.py` under `caffeinate` with `time` (:25).
- **In.** Run name plus `run_subset.py` args. **Out.** `logs/<name>_<timestamp>.log`.
- **Calls upstream.** None directly (through `run_subset.py` and `verify_openie_cache.py`).
- **Deck.** Provenance for slide 4 (commit hash, 0-line diff).

### `experiments/stamp_openie_cache.py` (60 lines)
- **Purpose.** The shipped gpt-4o-mini OpenIE file has no `provenance` block, so HippoRAG rejects it. This writes a stamped copy to `<save_dir>/<working_dir>/openie_state.json`, so OpenIE makes 0 calls.
- **In.** `outputs/musique/openie_results_ner_gpt-4o-mini.json`, `--save_dir`, `--llm_name`, `--llm_base_url`. **Out.** the stamped `openie_state.json`.
- **Calls upstream.** `HippoRAG(...)` (constructed only to read the expected provenance), `BaseConfig`.
- **Deck.** Backup "cost": OpenIE cost ₹0, because the shipped extractions are reused (caveat: the prompt can't be verified).

### `experiments/verify_openie_cache.py` (93 lines)
- **Purpose.** A network-blocked pre-launch guard. It rebuilds `run_subset.py`'s exact BaseConfig (stubbed RAG classes, `_Stub` :56), constructs HippoRAG and asks `load_existing_openie` how many chunks still need OpenIE. It exits 0 only if that number is 0. `--extra_docs` covers the extension's injected passages.
- **Key functions.** `_blocked` :22 (network block), `_Captured` :49, `_Stub` :56.
- **Calls upstream.** `HippoRAG(...)`, `HippoRAG.load_existing_openie`, `compute_mdhash_id` (`src/hipporag/embedding_store.py`).
- **Deck.** Backup "cost" (0 OpenIE chunks in every run and cell).

### `experiments/share_chunks_to_dense.py` (62 lines)
- **Purpose.** Seeds the dense run's chunk store with HippoRAG's own passage vectors (copies the parquet after `StandardRAG` writes its manifest). Both systems then rank identical passage vectors, so the comparison isolates the graph.
- **Key functions.** `Stub` :24 (config capture).
- **In.** `outputs/hipporag_n100_musique/.../chunk_embeddings/vdb_chunk.parquet`. **Out.** the dense save dir's chunk store (sha256-identical).
- **Calls upstream.** `StandardRAG(...)` (`src/hipporag/StandardRAG.py`), `compute_mdhash_id`.
- **Deck.** Slide 4 methods note ("same embedder, same passage vectors").

### `experiments/bootstrap_gap.py` (82 lines)
- **Purpose.** Paired bootstrap 95 % CIs for the HippoRAG 2 − dense gap: 10,000 resamples of questions, seed 0, percentile CI.
- **Key functions.** `per_question` :29 (scores each question with the repo's evaluators), `main` :42.
- **In.** two `per_query_n<N>.json` files, `--first N`. **Out.** stdout, saved as `results/musique_n500/bootstrap_n{100,500}.txt`.
- **Calls upstream.** `RetrievalRecall` (`src/hipporag/evaluation/retrieval_eval.py`), `QAF1Score`, `QAExactMatch` (`src/hipporag/evaluation/qa_eval.py`).
- **Deck.** Slide 4: Recall@5 gap +5.90 [+3.73, +8.00] and F1 gap +4.66 [+1.52, +7.69] at n = 500 (`results/musique_n500/bootstrap_n500.txt`).

### `experiments/smoke_test_gateway.py` (50 lines)
- **Purpose.** The smallest paid check of the AICredits gateway: one chat call and one embedding call; it prints the resolved model IDs and token usage. `scrub` :24 removes the key from error text.
- **Calls upstream.** None (OpenAI SDK directly). **Deck.** None (setup).

---

## Theory

### `experiments/theory/verify_margin.py` (138 lines) and `test_verify_margin.py` (10 lines)
- **Purpose.** Re-derives the toy-graph PPR closed forms with sympy from the balance equations, and checks them against igraph PRPACK on the full toy graph (480 random resets).
- **Key functions.** `equations` :37, `solve` :52, `full_graph_ppr` :56, `main` :83 (`check` :86). The test asserts exit 0 (:6).
- **In.** None. **Out.** stdout pass/fail per formula; exit code.
- **Calls upstream.** None (sympy + igraph; it uses the same `personalized_pagerank(..., directed=False, implementation='prpack')` convention as `HippoRAG.run_ppr`).
- **Deck.** Slide 5: Graph A x = y = d/((1+d)(n+k)); Graph B x = y = d/((2+d)(n+k)); margin Δ ∝ dσ(1/n² − 1/k²); agreement to 2.2e-16 (PROGRESS.md, Session 7).

---

## Extension: update resistance (`experiments/extension/`)

### `common.py` (96 lines)
- **Purpose.** Shared paths, the base index location (`BASE_SAVE_DIR` :23), launch args (:31–36) and prices (`PRICE_USD_PER_M`, `INR_PER_USD`, `GATEWAY_MULTIPLIER` :39–41). `capture_config` :53 returns the BaseConfig `run_subset.py` would build, so cells cannot drift from the reproduction config. Also `inr` :44, `launch_args` :48, `word_pattern` :85, `contains_phrase` :90, `chunk_text` :94.
- **Calls upstream.** `text_processing` (`src/hipporag/utils/misc_utils.py`, the graph's entity normalizer).
- **Deck.** Every ₹ figure (backup "cost") uses these constants.

### `select_targets.py` (249 lines): targets v1 (superseded)
- **Purpose.** Offline target selection. It finds questions with exactly one answer-object triple (s, r, o) (the anchor, `find_anchor` :65), draws o′ from same-relation objects (`replacement_candidates` :100), swaps the text (`swap_passage` :127) and stratifies by frequency (`select_targets` :185). Also `build_corpus_index` :43, `text_frequency` :60, `find_eligible` :141, `make_target` :162.
- **In.** MuSiQue sample, the base OpenIE state. **Out.** `data/targets.jsonl` (120 targets).
- **Calls upstream.** None at runtime (it reads the OpenIE JSON).
- **Deck.** Slide 6 / backup: v1 → v5 history ("why the targets changed").

### `select_targets_v2.py` (277) and `select_targets_v3.py` (238): superseded pickers
- **v2.** o′ picked by gpt-4o-mini from ≤ 8 same-relation candidates ranked by entity-vector cosine (`ranked` :66, `build_messages` :84, `select_v2` :143). Out: `data/targets_v2.jsonl`; 78 selected.
- **v3.** Collision groups instead of drops (`assign_groups` :107, `check_groups` :127, also used by `finalize_targets.py`), a 1–5 plausibility rater (`plausibility_messages` :84) and the doubled-token check (`doubled_token_hits` :68). Out: `data/targets_v3.jsonl`, `data/review_v3.md`; 32 kept.
- **Calls upstream.** `CacheOpenAI` (`src/hipporag/llm/openai_gpt.py`) for the paid calls.
- **Deck.** Backup (target-pipeline history).

### `select_targets_v4.py` (253 lines)
- **Purpose.** o′ is *generated* by gpt-4o-mini (3 candidates; `generation_messages` :80, `parse_candidates` :93); the first candidate passing the offline checks is used (`check_candidate` :104). One question per gold passage (`anchors_one_per_passage` :53).
- **Out.** `data/targets_v4.jsonl`, `data/review_v4.md`, `outputs/extension/target_generation_v4/generations.json`.
- **Calls upstream.** `CacheOpenAI`. **Deck.** Slide 6 (the swap design).

### `select_targets_v5.py` (245 lines)
- **Purpose.** Re-judges v4's swaps with three truth-blind yes/no checks (`check_messages` :72, `parse_checks` :86), and runs a closed-book knowledge probe (`probe_messages` :96, `knows` :102) that becomes the `model_knows_o` covariate. `review_markdown` :112.
- **Out.** `data/targets_v5.jsonl` (120 swaps), `data/review_v5.md`, `outputs/extension/target_checks_v5/checks_and_probe.json`.
- **Calls upstream.** `CacheOpenAI`, `normalize_answer` (`src/hipporag/utils/eval_utils.py`). **Deck.** Slide 6.

### `reprobe_v5.py` (123 lines)
- **Purpose.** Re-probes with the gold title + subject + relation, to disambiguate (`titled_probe_messages` :27, `merge` :33, `main` :51); sets `model_knows_o` (48 yes / 72 no over 120). Rewrites `targets_v5.jsonl` and `review_v5.md` (adds the keep column).
- **Calls upstream.** `CacheOpenAI`. **Deck.** Slide 6 (covariate).

### `finalize_targets.py` (85 lines)
- **Purpose.** Reads the hand marks in `review_v5.md` (`read_marks` :25), checks they cover exactly the 120 targets (`finalize` :44, which uses `check_groups`), writes `data/targets_final.jsonl` and prints bin counts and which analysis splits are used (`report` :54).
- **In.** `data/review_v5.md`, `data/targets_v5.jsonl`. **Out.** `data/targets_final.jsonl`.
- **Calls upstream.** None. **Deck.** Slide 6: N = 75 swaps after screening; `model_knows_o` split used, o′-frequency split not used (`data/review_reasons.md`).

### `inject.py` (106 lines)
- **Purpose.** Deterministic injection with no LLM. A variant is the gold passage (old) or the swapped passage (new) with a distinct title line (`variant_tag` :30, `variant_title` :35, `make_variant` :39). `cell_variants` :58 builds the (n, k) cell; `all_variants` :70; `as_chunks` :75; `openie_rows` :81 and `append_openie_rows` :87 copy the cached triples (o → o′) into the clone's OpenIE state, with provenance kept.
- **Calls upstream.** `compute_mdhash_id`, `Chunk` (`src/hipporag/utils/misc_utils.py`). **Deck.** Slide 6 (grid design).

### `vectors.py` (187 lines)
- **Purpose.** Embed once, reuse everywhere. Plans every passage, fact, entity and query text a cell needs (`plan_texts` :107), embeds each exactly once (`embed_plan` :132, the only paid line, `model.batch_encode` :138), and stores them in a `VectorTable` (:56). `FrozenEmbedder` (:33) serves cells and raises on any unknown text, so cells make 0 embedding calls by construction. Also `fact_strings` :92, `entity_strings` :97, `store_ids` :101, `count_tokens` :143.
- **Out.** `outputs/extension/<run_id>/vectors.npz`.
- **Calls upstream.** `_get_embedding_model_class` (:175), the embedding model's `batch_encode`, `compute_mdhash_id`.
- **Deck.** Backup "cost" (embed-once ≈ ₹0.22).

### `cell_index.py` (72 lines)
- **Purpose.** Per-cell index = APFS clone of the base save dir (`clone_base` :35, `cp -c`; LLM cache shared through a symlink), plus the injected OpenIE rows (`prepare_cell` :54), plus an incremental index of only the injected chunks with OpenIE replaced by a sentinel that raises (`NoOpenIE` :28, `index_cell` :60). `remove_cell` :70.
- **Calls upstream.** `HippoRAG.index` (:65). **Deck.** Slide 6 ("experiments never modify the base index").

### `attrib_rag.py` (232 lines)
- **Purpose.** Retrieval with per-stage records and the fix, without editing src/.
  - `AttributionHippoRAG(HippoRAG)` :52 overrides `rerank_facts` :76 (records stage A = top-5 candidate facts with scores, stage B = filter-kept facts, then calls upstream) and `run_ppr` :96 (records the reset vector and passage scores, then calls upstream).
  - `trace_query` :130 is the body of upstream `retrieve()`'s per-query loop.
  - `attribute` :150 builds one record per (question, cell): seeds, best old/new scores, top 5, correction@5, contamination@5, and the dense arm on the same query vector.
  - `install_frozen_embedder` :60, `preload_query_vectors` :66.
  - The fix: `FixedHippoRAG` :231 with `drop_superseded` :109 (among kept facts sharing `canonical_fact_key` :27, keep only the newest by `fact_recency` :104). `outranks_old` :37 applies the relative tie tolerance.
- **Calls upstream.** `HippoRAG.get_query_embeddings`, `get_fact_scores`, `rerank_facts` (→ `rerank_filter`, `src/hipporag/rerank.py`), `graph_search_with_fact_entities`, `run_ppr`, `dense_passage_retrieval`, `prepare_retrieval_objects`; `compute_mdhash_id`.
- **Deck.** Slides 7–8: every per-record field behind correction resistance and the attribution; slide 3 demo (via `demo/`).

### `long_context.py` (65 lines)
- **Purpose.** The long-context reader arm. It gives the reader the question's own paragraphs plus every injected variant, in a seeded shuffle (`reader_passages` :33, `build_messages` :41, the same `rag_qa_musique` template via `_manager` :26). It labels the answer o / o′ / both / neither (`parse_answer` :48, `classify` :59).
- **Calls upstream.** `PromptTemplateManager` (`src/hipporag/prompts/prompt_template_manager.py`), `normalize_answer`.
- **Deck.** Backup "long-context corners" (1,1), (1,5), (3,1), (3,5).

### `run_cells.py` (444 lines)
- **Purpose.** The grid runner, n ∈ {1, 3} × k ∈ {0, 1, 2, 3, 5}. It has three modes:
  - `--dry-run` (`dry_run` :139, `filter_plan` :78, `reader_tokens` :89, `disk_plan` :118);
  - `--measure`, an offline rehearsal on the real base with random vectors and a fake filter (`rehearse` :338, `_block_network` :191, `_KeepTopTwo` :200, `random_table` :210);
  - `--confirm-paid` (`run` :373, `run_long_context` :398).

  The core is `execute_cell` :222, which clones, injects, indexes, attributes both arms and runs the gates (`_gate` :331). Also `cell_prefix` :51, `groups_of` :55, `ids_for` :68.
- **Out.** `outputs/extension/<run_id>/results/cell_n*_k*_g*.jsonl`, `cell_stats.jsonl`, `long_context_*.jsonl` (sealed; hashes in PROGRESS.md).
- **Calls upstream.** `HippoRAG` (:307), `CacheOpenAI` (:400), `PromptTemplateManager` (:106), `compute_mdhash_id` (:69), chunk store `get_row` (:314), `close` (:322); plus everything through `attrib_rag.py` and `cell_index.py`.
- **Deck.** Slide 6 (grid, gates, cost) and the raw records behind slides 7–9.

### `analysis.py` (517 lines)
- **Purpose.** Offline analysis of the sealed grid.
  - Loading: `load_records` :110, `restrict_to_final` :100 (`--final targets_final.jsonl`), `flatten` :117.
  - Metrics by (n, k) × slice × arm: `summarize` :143, slices from `slice_map` :79.
  - First-failure attribution A → B → C → D → E_tie / E_crowd: `first_failure` :56, `attribution_counts` :164.
  - Paired bootstrap: `paired_bootstrap` :184, `bootstrap_all` :207.
  - LaTeX tables: `latex_tables` :219. Figures: `plot_lines` :329, `plot_stacks` :368. Trace printer: `print_trace` :401. Entry point: `main` :434.
- **Out.** `metrics.csv`, `attribution.csv`, `bootstrap.csv`, `summary.md`, 4 PNGs (:467–513), and `paper/tables/tab_{main,bootstrap,attribution,tolerance}.tex`.
- **Calls upstream.** None (it reads records).
- **Deck.** Slides 7, 8 and 9: correction@5, contamination@5, outranks, attribution counts, fix vs no-fix CIs. First run on real results on 2026-11-16, after prediction commit `460c50a`: `analysis/grid_v5_final/`.

### `phase_b.py` (369 lines)
- **Purpose.** Offline supplement to `analysis.py` for the prediction items. `compute` :61 builds:
  - the funnel (fact among the 5 candidates, kept by the filter, both kept) :68;
  - filter keep rates overall and by `model_knows_o` :88;
  - the both-kept tie and dense-agreement check :121;
  - the n = 1 → 3 change with paired bootstrap :141;
  - pooled correction@5 and contamination@5 :153;
  - fix-vs-no-fix detail and other-gold recall :174;
  - where failures sit :203;
  - long-context labels :233.

  `boot_ci` :40, `row_ids` :52 (review row number → target id, for `--drop_rows`), `markdown` :255, `main` :333.
- **In.** `results/extension/grid_v5_20261109/*.jsonl`, `data/targets_v5.jsonl`, `data/targets_final.jsonl`, `data/review_v5.md`, `reproduce/dataset/musique.json`.
- **Out.** `<out>/phase_b.json`, `phase_b.md`, `targets_used.txt` (`analysis/grid_v5_final/` and `analysis/grid_v5_final_minus_specialist/`).
- **Calls upstream.** None (it reads records; uses `analysis.load_records`, `restrict_to_final`, `attrib_rag.outranks_old`).
- **Deck.** Slide 7 (stale-copy change −11.7 vs −0.7), slide 8 (funnel 75 → 9 → 8 → 7, fix +0.2), slide 9 (prediction table), backup long-context table; `RESULTS_BRIEF.md` throughout.

### `followup.py` (284 lines)
- **Purpose.** Follow-up analyses on the existing records (offline). `compute` builds: the interaction CI for the n = 1 → 3 penalty (tests prediction item 4); the k = 0 baseline for the old fact and the route by which passages reach the top 5 without their fact (`route`, `route_summary`; exploratory); the penalty split by o′ absent/present and the lost-at-n = 3 table with node degrees (exploratory). `boot_diff_groups` (two independent groups), `spearman`, `markdown`, `main`.
- **In.** The sealed grid records, `data/targets_final.jsonl`, and the n = 3 cell graphs `outputs/extension/grid_v5_20261109/cell_n3_k*_g*/…/graph.pickle` (read-only, for degrees).
- **Out.** `analysis/grid_v5_final/followup.json`, `followup.md`.
- **Calls upstream.** `compute_mdhash_id`, `text_processing` (entity node keys); igraph `degree` / `strength` on the stored graph.
- **Deck.** Slide 7 (interaction −11.0 [−16.7, −6.0]; 18 worse / 0 better), slide 8 (old fact a candidate for 9 of 75; 34 of 66), slide 9 (`deck/figs/route.pdf`: 71 / 114 / 64 of 249), slide 11 (open question).

### `tests/test_extension.py` (717 lines)
- **Purpose.** Offline tests on a synthetic corpus, with a fake embedder (:68), fake LLM (:88) and fake OpenIE (:103), and the network blocked (:27). Key checks:
  - `test_trace_matches_upstream_retrieve` :253 (the tracer equals upstream `retrieve()`);
  - `test_fix_drops_older_conflicting_fact` :302;
  - `test_filter_prompt_repeats_across_k_ge_1_cells` :335;
  - `test_base_untouched` :356;
  - `test_capture_config_matches_launch` :383.
- **Calls upstream.** `HippoRAG.index`, `BaseConfig`, `NerRawOutput`, `TripleRawOutput`. **Deck.** Backup / viva ("how do you know the tracer is faithful").

### Data (`experiments/extension/data/`)
| File | What | Made by |
|---|---|---|
| `targets.jsonl` | v1, 120 targets (superseded) | `select_targets.py` |
| `targets_v2.jsonl` / `targets_v3.jsonl` + `review_v3.md` | v2 78, v3 32 (superseded) | v2 / v3 pickers |
| `targets_v4.jsonl` + `review_v4.md` | 58 rated 4–5 (superseded) | `select_targets_v4.py` |
| `targets_v5.jsonl` + `review_v5.md` | 120 swaps the grid ran on; hand marks in `review_v5.md` | v5 + `reprobe_v5.py` |
| `review_reasons.md` | one-line reason per keep mark, spot-check sample, finalize counts | hand review, 2026-11-16 |
| `targets_final.jsonl` | 75 swaps used by the analysis | `finalize_targets.py` |

---

## Figures and demo

### `paper/figs/make_figures.py` (156 lines)
- **Purpose.** Results-independent figures (PDF + 300-dpi PNG): `pipeline` :34 (stages A–E with the failure point at each), `toy_graph` :77, `repro_gap` :123 (n = 100 slice vs n = 500 vs the paper, with the bootstrap CIs). `save` :27.
- **In.** Numbers copied from PROGRESS.md Session 4 (no results files are read). **Out.** `paper/figs/{pipeline,toy_graph,repro_gap}.{pdf,png}`.
- **Calls upstream.** None. **Deck.** Slide 3 (pipeline), slide 4 (repro_gap), slide 5 (toy_graph).

### `demo/demo_lib.py` (424 lines)
- **Purpose.** Live and replay tracing for Presentation 2.
  - `trace_question` :163 runs one question through `AttributionHippoRAG.trace_query` on an APFS clone of the n = 500 index. It records the top-5 query→triple matches, the filter's input and output, the seed weights (entities, plus passages at dense × `passage_node_weight`), the all-node PPR top 10 (recomputed with `run_ppr`'s exact igraph call and asserted equal to upstream's passage scores), HippoRAG and dense top 5 with gold marked, and the reader's answer with F1/EM.
  - `CallMeter` :107 counts paid filter/reader calls (cache hits excluded) and query-embedding tokens.
  - `make_index` :42 creates the clone. `build_rag` :97 uses `capture_config`. `load_key` :83 reads the key without printing it.
  - `render_terminal` :279, `render_markdown` :331, `graph_stats_markdown` :388.
- **In.** `demo/index/hipporag_n500_musique/` (clone of `outputs/hipporag_n500_musique`), `reproduce/dataset/musique.json`, `results/musique_n500/*_per_query_n500.json`.
- **Out.** `demo/traces/q<N>.{json,md}`, `demo/graph_stats.md`.
- **Calls upstream.** `HippoRAG.qa`, `dense_passage_retrieval`, `prepare_retrieval_objects`, the chunk store's `get_row`, `igraph.Graph.personalized_pagerank` (same arguments as `HippoRAG.run_ppr` :2204–2212), `QAF1Score`, `QAExactMatch`, `QuerySolution`; everything in `attrib_rag.trace_query`.
- **Deck.** Slide 3 (LIVE DEMO); backup "PPR maths" (the reset-mass split); `graph_stats.md` for slide 3 / backup.

### `demo/run_demo.py` (111 lines)
- **Purpose.** The CLI. By default it replays a saved trace offline (`main` :61). `--live` reruns retrieval; `--damping` / `--passage_weight` set live tweaks and print a comparison with the saved trace (`compare` :49, by chunk id). Other flags: `--save`, `--pause`, `--list`, `--make_index`, `--graph_stats`. Flag validation is in `parse_args` :28.
- **Calls upstream.** Through `demo_lib`; `rag.prepare_retrieval_objects` :93, `rag.close` :98.
- **Deck.** Slide 3 (LIVE DEMO), and the viva's "predict before you run" questions.

---

### `deck/make_figs.py` (76 lines)
- **Purpose.** Deck figures from the analysis outputs, with no hand-typed values: `correction` :28 (correction@5 vs k for n = 1 and n = 3, from `metrics.csv`) and `funnel` :53 (75 → 9 → 8 → 7 at n = 1, k = 1, from `phase_b.json`).
- **Out.** `deck/figs/correction.pdf`, `deck/figs/funnel.pdf`. **Calls upstream.** None. **Deck.** Slides 7, 8 and 9 (`route` reads `followup.json`).

## `results/` (evidence copies, not code)
- `results/musique_n500/`: per-query files and bootstrap outputs for the reproduction (README with sha256).
- `results/extension/grid_v5_20261109/`: sealed grid records (opened on 2026-11-16 after prediction commit `460c50a`; seal matched).
- `analysis/grid_v5_final/`, `analysis/grid_v5_final_minus_specialist/`: outputs of `analysis.py` and `phase_b.py` on the 75 final swaps, and on the 67 without the specialist-knowledge rows.
