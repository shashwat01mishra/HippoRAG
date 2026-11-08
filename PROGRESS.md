# Progress log

## 2026-10-14: Session 1: setup (no experiment runs, $0 API spend)

**Repo.** I forked OSU-NLP-Group/HippoRAG to shashwat01mishra/HippoRAG and cloned it to `C:\s_50\NLP project`. `upstream` points to the original repo. Tag `upstream-base` = `d5c8329` (upstream main on this date, package 2.0.0a5; the tag is local only). Work happens on branch `dev`, and `main` is identical to upstream.

**Platform decision.** I'm using WSL2 Ubuntu 26.04, because tmux needs Linux and a Windows venv can't be used from WSL. The repo lives on the Windows drive (`/mnt/c/s_50/NLP project`), and `.venv` is a Linux venv (Python 3.10.22 via uv 0.13.1, `UV_LINK_MODE=copy`). tmux 3.6 was already installed in WSL. The Windows side has Python 3.12/3.11, git 2.52, gh 2.98 and uv 0.12.1, and no Python 3.10. I/O on `/mnt/c` is slow; importing torch takes minutes on a cold start.

**Install.** `uv pip install -e .` works (torch 2.5.1+cu124 with no GPU visible, so CPU only). `from hipporag import HippoRAG` imports. Offline unit tests: **93/93 pass**. I skipped `tests/integration/` because it hits paid APIs.

**Secrets.** `.env` holds `OPENAI_API_KEY=` and is gitignored. Nothing in the code loads `.env` (there's no python-dotenv), and the OpenAI SDK reads `OPENAI_API_KEY` from the environment. So each shell needs `set -a; source .env; set +a`.

**Data.** `reproduce/dataset/musique.json` (12.5 MB, 1,000 questions) and `musique_corpus.json` (6.2 MB, 11,656 passages) already ship in git. The HF copies are sha256-identical. `osunlp/HippoRAG_v2` is a redirect to `osunlp/HippoRAG_2`, so they're the same dataset repo.

**OpenIE cache.** The shipped `outputs/musique/openie_results_ner_gpt-4o-mini.json` (11,656 docs) has the right path and name but **no `provenance` block**, so `HippoRAG.__init__` rejects it with `StateConsistencyError` (verified offline). The fix needs no src edit: `python experiments/stamp_openie_cache.py` writes a copy with the expected provenance to `outputs/musique/gpt-4o-mini_text-embedding-3-small/openie_state.json`, which is read first. Verified offline: all 11,656 corpus chunks are cached, so OpenIE makes 0 API calls. The provenance must be computed through `src.hipporag` imports, as `main.py` does, because it records class module paths. Caveat: the stamp asserts that the shipped extractions came from the current prompt and settings, and I can't verify that.

**Gotcha.** HippoRAG and StandardRAG use the same working dir (`<save_dir>/gpt-4o-mini_text-embedding-3-small`), and their index manifests conflict (`rag_type`). So the dense baseline needs its own `--save_dir`.

**Incident.** A quoting bug made one offline verification run write the stamped file into the real `outputs/musique/`. I deleted it the same session; `outputs/` again matches upstream.

**Code map.** See `notes/code-map.md`.

**Next.** Fill in `.env`, then do the sample sanity run (< $0.01), the dense baseline (~$0.3–0.5), and the HippoRAG run on MuSiQue after stamping.

## 2026-10-16: Session 2: move to WSL filesystem (no experiment runs, $0 API spend)

- Pushed `dev` (`f40d4c3`) and the `upstream-base` tag (`d5c8329`) to origin. The fork also has upstream's `backup-main` and `develop` branches, which were copied in when the fork was made.
- The new working copy is `~/nlp-hipporag` (WSL ext4), on `dev`, with tags fetched and `upstream` added. `.venv` was recreated (Python 3.10, uv); the unit tests pass **93/93**. `.env` was copied over (`chmod 600`, key still empty). `/mnt/c/s_50/NLP project` is left untouched until the new copy is confirmed.
- WSL git: identity is set to match Windows. Push auth goes through the Windows Git Credential Manager (`credential.helper`), with no gh in WSL and no sudo. A `git push --dry-run` authenticates OK.
- `outputs/musique/openie_results_ner_meta-llama_Llama-3.3-70B-Instruct.json` is 24,191,460 bytes, with 11,656 docs and 144,511 triples (gpt-4o-mini: 127,640 triples). It also has no `provenance` block, so it would be rejected like the gpt-4o-mini file. Not stamped.
- CLAUDE.md now has three more rules: every run gets its own `--save_dir`; base indexes are copied per condition, never modified; offline temp-dir verification is OK, but writing under `outputs/` is not.
- The run commands now use their own save dirs (`outputs/sanity_sample`, `outputs/dense_musique`, `outputs/hipporag_musique`). The stamp targets `outputs/hipporag_musique`.
- Incident: a shell-quoting bug in a commit command executed backticked words from the log text as commands in WSL. Everything failed harmlessly (command-not-found, plus a repeated `git push --dry-run`). I checked afterwards: no files changed, no commit, remote unchanged.
- The unit tests leave an empty `outputs/gpt-4o-mini_nvidia_NV-Embed-v2/`. I left it in place (outputs/ rule).

## 2026-10-16: Session 2 (cont.)

- Pushed `3e75020` to origin `dev`.
- With explicit authorization, `rmdir`'d the empty `outputs/gpt-4o-mini_nvidia_NV-Embed-v2/` in `~/nlp-hipporag`.
- New CLAUDE.md rule: multi-line text goes through the file-write tool, never shell strings (two quoting incidents in two sessions).
- Sanity run (a) was reported as passed, but no trace of it was found: there's no `logs/sanity_sample_*.log` and no `outputs/sanity_sample/` in either copy or under `~`/`/tmp`, and both `.env` files still have an empty key. So the deletion of `/mnt/c/s_50/NLP project` is on hold pending the user's confirmation. That copy is clean (no uncommitted changes, unpushed commits or stashes), so it holds nothing that isn't on GitHub, apart from a rebuildable `.venv` and an empty `.env`.

## 2026-11-08: Session 3: move to MacBook Pro M5 (no experiment runs, $0 API spend)

- The Windows/WSL laptop is unreachable (dead screen). Both WSL copies are gone with it; GitHub `dev` was complete, so nothing was lost. The Session 2 open item (deleting `/mnt/c/s_50/NLP project`) is moot.
- Cloned `dev` to `~/nlp-hipporag` on macOS (arm64), fetched tags, added `upstream`. Verified HEAD = `3c01a1e`, `upstream-base` = `d5c8329`.
- Installed via Homebrew: uv 0.13.7, tmux 3.8, gh 2.103.3.
- `.venv`: Python 3.10.22 (uv-managed, aarch64), same patch version as on WSL. `uv pip install -e . pytest` installed cleanly on arm64; `uv pip check` reports all 81 packages compatible. torch 2.5.1 is the macOS build (CPU + MPS available, no CUDA); `from hipporag import HippoRAG` imports.
- Offline unit tests (excluding `tests/integration/`): **93/93 pass**, in 7.6 s (WSL on `/mnt/c` took minutes just to import torch). As before, the tests leave an empty `outputs/gpt-4o-mini_nvidia_NV-Embed-v2/`; left in place (outputs/ rule).
- `.env` created with an empty `OPENAI_API_KEY=`, `chmod 600`, gitignored (`.gitignore:24`). Key not yet filled in.
- Git on this Mac: no identity was configured; set to match previous commits (`Shashwat <shashwatmishravats@gmail.com>`). Credential helper is `osxkeychain`; gh is not logged in, so push auth is not yet set up.
- CLAUDE.md: scope replaced with the revised scope from 23 Oct (after Presentation 1); deadlines updated (Eval 2 planned for 13 Nov, paper 14 Nov, may move); platform note added.
- Not yet done (carried over from Session 1): sample sanity run, dense baseline, HippoRAG MuSiQue run with the stamped OpenIE cache.
- After the commit, the repo was moved to `~/work/S50/nlp-hipporag` (the path above is outdated); `.venv` was rebuilt there and the tests pass 93/93 again.

## 2026-11-08: Session 4: gateway setup, sanity run, 100-query subset (both modes)

### Methods details
- **Gateway.** All LLM and embedding calls go through AICredits (`https://api.aicredits.in/v1`), an OpenAI-compatible, rupee-billed gateway; I can't pay OpenAI directly. Key in `.env` as `OPENAI_API_KEY`, loaded per shell. Model IDs: `gpt-4o-mini` (the gateway resolves it to `gpt-4o-mini-2024-07-18`, the snapshot that produced the shipped OpenIE extractions) and `text-embedding-3-small` (1,536-d). Smoke test: `experiments/smoke_test_gateway.py`.
- **Embedding routing.** `main.py` has no flag for `embedding_base_url`, so in `main.py` runs the embedding client falls back to the env var `OPENAI_BASE_URL` (the sanity run used this; its manifest records `embedding.base_url: null`). From the subset on, runs use `experiments/run_subset.py`, which passes `embedding_base_url` explicitly, so it is recorded in BaseConfig and the index manifest; `OPENAI_BASE_URL` is unset at launch.
- **`max_tokens`.** For non-OpenAI hosts that aren't registered gateways, HippoRAG sends `max_tokens` rather than `max_completion_tokens` (`chat_max_tokens_key`, `llm/gateways.py`).
- **Stamp caveat.** The stamp asserts that the shipped extractions came from the current OpenIE prompt and settings. The model snapshot matches; the prompt cannot be verified.
- **Stamp provenance** records `llm_name` and `llm_base_url`, so a stamp is per model ID and endpoint. A stamp made for `api.openai.com` is rejected with the gateway URL (verified). `stamp_openie_cache.py` now takes both as required args.
- **Shared passage vectors.** The dense run reuses HippoRAG's chunk embeddings (`experiments/share_chunks_to_dense.py`), so both modes rank with identical passage vectors and the comparison isolates the graph. Verified before copying: HippoRAG's preprocessing leaves MuSiQue docs unchanged (same texts, same IDs), same namespace and file layout, identical manifest `embedding` sections and embedding model class. StandardRAG writes its own manifest on the empty store first; the parquet is then copied (sha256-identical) and reopens with 11,656 rows matching the corpus.
- **Subset.** Each subset is the first N questions of the authors' 1,000-question MuSiQue sample (`reproduce/dataset/musique.json`, file order), not a fresh random draw; the full 11,656-passage corpus is always indexed. BaseConfig of `run_subset.py` vs `main.py` with identical flags: 68 fields, only `embedding_base_url` differs.
- **`--embedding_batch_size 128`** (default 8). Can't change results: slices are sent sequentially and reassembled by the API's `index` field (checked), normalization is per row, and the batch size is not in the manifest.
- **Guards.** `experiments/launch_run.zsh` refuses a dirty tree, logs commit + `src/`/`main.py` diff vs `upstream-base`, and for HippoRAG runs executes `experiments/verify_openie_cache.py` with the exact launch args, aborting unless OpenIE would process 0 chunks (tested both ways).
- **Interruptions.** The LLM cache (`<save_dir>/llm_cache/*.sqlite`) commits each call, so reruns are free for completed calls in the same save_dir. Embedding passes are not resumable: a store is written once at the end of its pass.

### Runs (all code at `6cca5b0`, `src/` and `main.py` identical to `upstream-base`)
| Run | Save dir | n | Recall@5 | F1 | EM | Wall time | Tokens | Est. ₹ (list × 1.3) |
|---|---|---|---|---|---|---|---|---|
| sanity (`main.py`) | `outputs/sanity_sample` | 1 (3 passages) | 1.0 | 0.0 | 0.0 | 30 s | 6.4k in / 1.0k out | ₹0.135 (list) |
| HippoRAG 2 | `outputs/hipporag_n100_musique` | 100 | 59.75 | 48.48 | 38.0 | 100 min (91 min embedding) | LLM 428k in / 15.3k out; embed 3.88M | ₹17.29 |
| Dense | `outputs/dense_n100_musique` | 100 | 55.25 | 40.30 | 31.0 | 3.7 min | LLM 141k in / 9.8k out; embed queries only | ₹3.09 |

- Paper (Llama-3.3-70B + NV-Embed-v2, n=1,000): Recall@5 74.7 vs 69.7 (+5.0), F1 48.6 vs 45.7 (+2.9). Here at n=100: Recall@5 +4.5, F1 +8.2. n=100 is too small to read the F1 gap; the full run decides.
- Sanity F1 0: the reader answered "David Eagleman" (gold "Thomas C. Sudhof") with the gold passage at rank ≤ 2, so this is a reader error, not a pipeline fault.
- Embedding throughput was about 43 items/s at batch 128, so the HippoRAG index took 91 min (my estimate was 25–45 min).
- Logs: `logs/sanity_sample_20261108_113537.log`, `logs/hipporag_n100_20261108_143404.log`, `logs/dense_n100_20261108_161502.log`.

### Spend
- Smoke + sanity: ₹0.17 (key usage; list estimate ₹0.135, so the multiplier is ~1.26; using 1.3 from now on).
- Subset: ≈ ₹20.4 estimated (list × 1.3); actual key usage to be recorded. Running total ≈ ₹20.6 of the ₹100 cap.
- **Actual (key usage after the subset): ₹17.58 total, so the subset cost ≈ ₹17.41** (estimate ₹20.4). Effective ≈ 1.11× list at ₹88/$, matching the gateway catalog. Multiplier from now on: **1.15×**. Wallet ₹82.42.

## 2026-11-08: Session 4 (cont.): 500-query subset, paired bootstrap CIs

### Decisions
- Option (a): 500 queries, both modes (full 1,000 deferred). Save dirs `outputs/hipporag_n500_musique` and `outputs/dense_n500_musique` are copies of the n=100 save dirs (working dir + `llm_cache`), so the index and the first 100 questions' LLM calls are free. Copying is allowed under "experiments never modify a base index": the n=100 dirs stay untouched. Neither manifest records any save-dir path.
- Same launcher and guards as the n=100 runs.
- `run_subset.py` now writes `<save_dir>/per_query_n<N>.json` (question, answer, top-5 docs, gold docs/answers, in sample order) after `rag_qa`. BaseConfig diff vs `main.py` unchanged (68 fields, only `embedding_base_url`). The n=100 runs predate the dump and the LLM cache stores responses only, so n=100 per-question scores can't be rebuilt offline; the n=100 CIs come from the first 100 questions of the n=500 runs, valid only if that slice reproduces the n=100 pooled numbers exactly (checked below).
- `experiments/bootstrap_gap.py`: paired bootstrap, resampling questions (10,000 resamples, seed 0, percentile 95% CI), per-question scores recomputed with the repo's evaluators. Tested offline on synthetic dumps, including a misaligned-pairing rejection.
- Extension planning: OpenIE won't run on injected passages (triples copied from the cache by a deterministic swap), so that cost line is dropped.

### Estimate (500-query run, 400 new questions, list × 1.15)
- HippoRAG 2: 400 × (4,284 in + 153 out) ≈ ₹29.7. Dense: 400 × (1,408 in + 98 out) ≈ ₹10.9. Query embeddings negligible. **Total ≈ ₹40.7**; leaves ≈ ₹41.7 under the ₹100 cap (≥ ₹15 margin required).

### Runs (code at `abac2cd`, `src/` and `main.py` identical to `upstream-base`; OpenIE guard: 0 chunks)
| Run | Save dir | n | Recall@5 | F1 | EM | Wall time | New LLM tokens | Est. ₹ (list × 1.15) |
|---|---|---|---|---|---|---|---|---|
| HippoRAG 2 | `outputs/hipporag_n500_musique` | 500 | 62.00 | 44.93 | 30.8 | 26 min | 1.71M in / 59.2k out | ₹29.6 |
| Dense | `outputs/dense_n500_musique` | 500 | 56.10 | 40.27 | 27.6 | 15 min | 560k in / 39.0k out | ₹10.9 |

- No index work: every embedding store logged "Inserting 0 new records"; only the 500 query embeddings were fetched.
- Logs: `logs/hipporag_n500_20261108_184611.log`, `logs/dense_n500_20261108_191236.log`. Per-query: `<save_dir>/per_query_n500.json`.
- **Cache check.** Expected 1,000 / 500 cache rows; got 1,002 / 500. HippoRAG filter calls: exactly 400 new (all first-100 filter calls hit). QA calls: 402 new; the 2 extra are questions 7 and 11, whose reader prompt changed so the cache missed. Likely cause (not verified): query embeddings are re-fetched and not bitwise reproducible, which can reorder the top-5 passages. Consequence: **reruns are not exactly reproducible at the answer level** even with the LLM cache.
- So the first-100 slice reproduces the n=100 run's Recall@5 (59.75) and EM (38.0) and all dense numbers, but HippoRAG F1 is 48.15 vs 48.48 logged. The n=100 CIs below are for that slice, not bit-for-bit for the n=100 run.

### Paired bootstrap 95% CIs (gap = HippoRAG 2 − dense; 10,000 resamples of questions, seed 0)
| n | Recall@5 gap [CI] | F1 gap [CI] | EM gap [CI] |
|---|---|---|---|
| 100 (first 100 of the n=500 runs) | +4.50 [−0.50, +9.67] | +7.84 [+0.49, +15.51] | +7.00 [−1.00, +15.00] |
| 500 | **+5.90 [+3.73, +8.00]** | **+4.66 [+1.52, +7.69]** | +3.20 [+0.00, +6.40] |

- Paper (n=1,000, Llama-3.3-70B + NV-Embed-v2): Recall@5 +5.0, F1 +2.9. Both paper gaps fall inside the n=500 CIs. At n=500 both gaps exclude 0.
- Per question at n=500: Recall@5 HippoRAG better 113 / dense better 52 / tied 335; F1 90 / 61 / 349.

### Spend
- n=500 runs: list ₹35.2 (from cache-metadata tokens), ≈ ₹40.5 at 1.15×, ≈ ₹39.1 at the observed 1.11×.
- **Actual: key usage ₹54.02 total, so the n=500 runs cost ₹36.44** (≈ 1.04× list at ₹88/$). Wallet ₹45.98; cap headroom ₹45.98.
- **Correction.** An earlier version of this entry (commit `3855662`) misread ₹45.98, the wallet balance, as key usage. That gave a cost of ₹28.40 and a prompt-caching explanation for it, with LLM 0.85× / embeddings 1.2× multipliers. All of that is withdrawn: the real cost is at about list price, so no discount needs explaining.
- **Multiplier from now on: ≈ 1.1× list for all calls** (subset 1.11×, n=500 1.04×).
- Decision: the full 1,000 is not run now. The remaining 500 questions are ≈ ₹44 list ≈ ₹48 at 1.1×, more than the ₹45.98 wallet; with the ₹15 margin they would need ≈ ₹20 top-up and the cap raised to ≈ ₹120.

### Evidence backup
- `results/musique_n500/`: both per-query files (sha256-identical copies), the bootstrap outputs for n=100 and n=500, and a README with provenance. Tracked in git (≈ 5.2 MB of JSON); no embeddings or caches.

## 2026-11-08: Session 5: extension harness, offline (no API calls, ₹0 spend)

- Built `experiments/extension/` (steps 1–7; file list in its README). `src/` and `main.py`: 0-line diff vs `upstream-base`. Tests: extension 21/21, upstream 93/93.
- Targets: 120 (60 rare o′, freq_graph = 1; 60 common, freq_graph 10–143, median 17.5) from 291 eligible questions (seed 0). 118/120 anchor on the last hop. `.gitignore` now un-ignores `experiments/extension/data/`.
- Relation-as-type proxy is noisy (e.g. "part of the FA Cup", "born in Sweden, Oregon"); targets need manual review before the run.
- Offline rehearsal on an APFS clone of `outputs/hipporag_n100_musique` (scratchpad, cell n=3,k=5, random stand-in vectors, fake filter, network blocked): `verify_openie_cache.py --extra_docs` reports 0 chunks needing OpenIE (12,496 cached); 0 embedding API calls (1,022 frozen vectors served: 840 passages + 182 facts, 0 entities); index 9.7 s, 0.088 s per traced query; 0.97 GB of non-shared disk per k≥1 cell. Base dir unchanged (inode/size/mtime of all 153 files).
- Dry-run, full grid at 120 targets: 240 filter calls ≈ ₹10.6, embed-once ≈ ₹0.20, so ≈ ₹10.8 without the long-context arm; 1,200 reader calls ≈ ₹64.3, so ≈ ₹75.1 with it. Disk 7.9 GB for all cells; wall ≈ 13 min + 45 min.

## 2026-11-09: Session 6: target v2 picker, analysis, attribution rule (offline, ₹0 spend)

### Decisions
- **Targets v2.** o′ is chosen by gpt-4o-mini: one call per eligible target, picking from ≤ 8 same-relation candidates that pass the surface checks (≤ 4 rare + ≤ 4 common, topped up), or "none". The anchors, strata, collision rules and the deterministic text/triple swap are unchanged from v1. **The triples stay copied from the OpenIE cache with o replaced, not extracted.** LLM cache: its own namespace, `outputs/extension/target_selection_v2/llm_cache`. Code: `select_targets_v2.py`. Not run yet: waiting for OK.
- **Canonicalization = oracle detection.** The fix keeps exact match on the normalized (subject, relation). The correction's triple shares the old triple's subject and relation by construction, so detection of the injected contradiction is perfect. The fix measures resolution under perfect detection; detection quality is out of scope. Known false-positive path: a multi-valued relation re-asserted by an injected variant. The analysis counts drops of non-target facts.
- **Tolerance at analysis time.** Records keep only raw best-new / best-old scores; `analysis.py` reports outranks / near-tie / loses at 0, 0.5 %, 1 % and 2 %.
- **Attribution.** First failing stage, configurable: A new fact not a candidate → B filter dropped it → C o′ not seeded → D margin favours old beyond the tolerance → E outranks or ties but outside the top 5.
- Run root approved: `outputs/extension/<run_id>/`. Free disk 841 GiB (7.9 GB needed). Long-context arm: four corners (1,1), (1,5), (3,1), (3,5) by default.
- **Correction to Session 5:** the v1 targets came from **271** eligible questions, not 291. 291 was from the run before the shape checks.

### Built / verified
- `select_targets_v2.py` (estimate: 271 calls, 65.8k input tokens, ≤ 2.2k output, ≈ ₹1.08). Example prompts show that some same-relation pools contain no item of o's fine type (e.g. no county for "Rockland County"), so "none" may be frequent.
- `analysis.py`: metrics by (n, k) × stratum × arm, tolerance sweep, attribution counts, fix-drop counts, 4 PNGs, `--trace` printer for stage A–E review.
- `run_cells.py` refactored: one `execute_cell` serves the rehearsal and the paid run. The paid run writes to `outputs/extension/<run_id>/`, checks free disk first, refuses to overwrite results, and has `--cells`, `--arms` and `--long_context` (corners).
- Full 10-cell offline rehearsal on clones of the real base (random vectors, fake filter, network blocked): every cell's OpenIE guard reported 0 chunks to extract, 0 embedding API calls, 4–8 s index per cell, ~0.084 s per traced query, ≤ 0.97 GB non-shared disk per cell. Base dir unchanged. The analysis ran end to end on those records (numbers meaningless by construction; all failures land in A).
- Dry-run at 120 v1 targets: grid ≈ ₹10.8 without the long-context arm; long-context at the four corners 480 reader calls ≈ ₹26.4.
- matplotlib 3.10.9 installed into `.venv` (not added to the upstream requirements).
- Tests: extension 26/26, upstream 93/93.

## 2026-11-09: Session 6 (cont.): targets v2 picker run (paid, ≈ ₹1.40)

### Decisions
- **matplotlib** (3.10.9, in `.venv`) is an **analysis-only dependency**: it's used only by `experiments/extension/analysis.py` for PNG figures. It isn't needed for indexing, retrieval or any reproduction run, and it isn't in the upstream `requirements.txt`.
- **Candidates.** Same-relation objects are ranked by cosine to o, using the base index's entity vectors (offline). Excluded: cosine ≥ 0.92, substrings either way, and answer aliases. The 8 nearest in the target's assigned stratum are offered; on "none" there is one retry with the other stratum, and the stratum change is logged.
- **Single-valued relations only.** Offline: drop the target if its subject has ≥ 2 distinct objects for the relation in the corpus (55 dropped). In the same picker call, gpt-4o-mini answers SINGLE yes/no, and "no" drops the target.
- **o′ is chosen by gpt-4o-mini; the triples stay copied from the OpenIE cache with o replaced, not extracted.**
- Fix collateral drops (non-target facts dropped by the fix) stay a reported metric (`metrics.csv` column, `summary.md` table).
- Attribution stage E split into **E_tie** (near tie, outside the top 5) and **E_crowd** (outranks old, outside the top 5).

### Run (code at `91ea29c`, tree clean)
- Log: `logs/targets_v2_picker_20261109_011557.log`. Picks with all candidates, responses and SINGLE answers: `outputs/extension/target_selection_v2/picks.json`. LLM cache: `outputs/extension/target_selection_v2/llm_cache/`.
- Estimate ₹1.17 (no retries) to ₹1.95 (all retries). Actual: 285 calls (14 cache hits: identical prompts), 85,212 in / 2,786 out tokens, ≈ **₹1.40** at list × 1.1. Key usage not yet checked.
- Yield: 216 prepared → 158 picked → **78 selected (53 rare, 25 common)**, below the 100–120 aim. Losses: 57 "none" after retry, 1 SINGLE = no, 80 entity/passage collisions. Of the 158 picks, 112 ended rare and 46 common; 18 selected targets changed stratum on retry.
- SINGLE answered yes 284 times and no once, so it filtered almost nothing; the offline corpus check did the work (55).
- Swap quality (20 printed): the rare stratum mostly reads plausibly (counties, actors, dates, record labels). The common stratum is still often implausible ("Jason Bourne series created by Walt Disney", "Time Warner Cable → United States Navy", "wedding to Charlemagne", "written by John Lennon"); frequent same-relation objects are generic. One type mismatch: "Scottish clan → Scottish indie rock band".
- `data/targets_v2.jsonl` written; run_cells/analysis defaults still point to v1, pending review of the swaps.
- **The SINGLE (single-valued) question in the picker call was ineffective: 284 yes / 1 no.** The offline corpus filter (subject with ≥ 2 objects for the relation: 55 dropped) did the actual filtering. Keep the offline filter; don't rely on the LLM answer.
- The 78 v2 targets were not accepted.

## 2026-11-09: Session 6 (cont.): targets v3 (paid, ≈ ₹0.31)

### Decisions
- **Groups instead of dropping collisions.** All picked targets are partitioned into collision-free groups by greedy colouring (most conflicts first). The strict rule holds within a group: no shared normalized s/o/o′ and no shared gold passage. Each group gets its own index per cell. Filter calls and the embed-once table are unchanged (each question is in exactly one group); indexing time and disk scale with the group count.
- **Plausibility pass.** One gpt-4o-mini call per picked target (own cache: `outputs/extension/target_plausibility_v3/llm_cache`) rates the swapped sentence alone 1–5 for "would an informed reader find this believable even if it is wrong", penalising anachronisms, category errors and wrong nationality or era. Keep 4–5.
- **Doubled-token check** at the swap boundary (word before o′ = o′'s first word, or word after = its last word). Hits are dropped, not edited.

### Run (code at `c22c0db`, tree clean)
- Log: `logs/targets_v3_plausibility_20261109_013404.log`; scores: `outputs/extension/target_plausibility_v3/scores.json`.
- Input: the 158 v2 picks, rebuilt offline from `picks.json` (112 rare, 46 common; no picker re-run).
- Estimate ₹0.44. Actual: 158 calls (42 cache hits), 18,876 in / 580 out tokens, ≈ **₹0.31** at list × 1.1.
- Scores: 1: 63, 2: 43, 3: 20, 4: 20, 5: 12. Rare 45/26/16/14/11, common 18/17/4/6/1.
- Doubled token: 1 hit ("emperor Emperor Wencheng"), dropped.
- **Kept: 32 (25 rare, 7 common), in 5 groups of sizes 20 / 6 / 4 / 1 / 1.**
- **Duplicates.** 65 of the 158 picks share an identical o→o′ swap with another pick (23 swaps): different MuSiQue questions on the same gold passage get the same sentence and the same pick. That is also why 42 rating calls were cache hits. The 32 kept targets come from only **21 distinct gold passages (17 rare, 4 common)**, and the extra groups exist mainly because of these shared passages.
- Dry-run at 32 targets / 5 groups: grid ≈ ₹2.90 without the long-context arm; four-corner long-context ≈ ₹7.11; non-shared disk ≈ 4.8 GB per k ≥ 1 cell, 39.4 GB for all cells (841 GiB free).
- Written: `experiments/extension/data/targets_v3.jsonl`, `experiments/extension/data/review_v3.md` (common first, then lowest score first). Defaults still point to v1. No cells run.
- v3 not accepted: 32 targets / 21 passages is too few.

## 2026-11-09: Session 6 (cont.): targets v4, generated o′ (paid, ≈ ₹0.98)

### Method change and reason
- **o′ is now generated, not picked.** v2/v3 chose o′ from objects that occur with the same relation elsewhere in the corpus. Those candidates were mostly implausible (v3: 106 of 158 picks rated 1–2; only 32 rated 4–5). v4 asks gpt-4o-mini for 3 replacements of the same fine-grained type that are plausible in the exact sentence and false (JSON reply; own cache `outputs/extension/target_generation_v4/llm_cache`). The first candidate passing the offline checks is used: not o, not an alias, no substring either way, not in the question's own paragraphs, same surface shape, no doubled token. The v3 plausibility rater then runs as a separate call (own cache `outputs/extension/target_plausibility_v4/llm_cache`); keep 4–5. The threshold was not lowered.
- **Unit of analysis = distinct gold passage.** One question per passage (seeded choice), and n is reported as distinct swaps.
- **Rare/common stratification dropped.** The corpus frequency of o and o′ (passages whose triples contain the entity; 0 if absent) is logged as a covariate. `analysis.py` splits by frequency only where every bin has ≥ 15 swaps.
- Collision groups recomputed on the v4 set. The single-valued offline filter stays; the SINGLE LLM question is gone.
- Generated o′ may be absent from the corpus. It then becomes a new entity node at indexing time, with its vector from the embed-once table (tested).
- Triples are still copied from the OpenIE cache with o replaced, not extracted.

### Run (code at `d442d00`, tree clean)
- Log: `logs/targets_v4_20261109_014739.log`; per-passage generations, checks and scores: `outputs/extension/target_generation_v4/generations.json`.
- Estimate (upper bound) ₹1.65. Actual: 139 generation + 132 rating calls, 52,197 in / 3,761 out tokens, ≈ **₹0.98** at list × 1.1.
- Funnel: questions with an anchor and passing the single-valued filter → **139 distinct gold passages** (160 questions shared a passage; this is the ceiling) → 132 with a candidate passing the offline checks (7 none; failures counted per candidate: 47 in own paragraphs, 7 shape, 5 doubled token, 1 each equals-s / alias / substring) → **58 rated 4–5** (scores 1: 19, 2: 37, 3: 18, 4: 46, 5: 12). The cap of 120 was not reached.
- Chosen candidate rank: 1st 109, 2nd 16, 3rd 7.
- **Yield: 58 distinct swaps, 2 collision groups (57 + 1).** o′ frequency: 0 (absent) 36, 1–9 13, ≥ 10 9. o frequency: 1–9 49, ≥ 10 9. No frequency split reaches 15 per bin except o′ absent (36), so `analysis.py` will report "all" only.
- Observation (not acted on): several 2–3 ratings look like believable swaps (Kamloops → Vancouver, Warner Music Group → Universal Music Group, Waseca County → Hennepin County, Hudson Bay → James Bay). The rater may penalise swaps whose true value it knows, i.e. it is rating truth more than believability.
- Written: `experiments/extension/data/targets_v4.jsonl`, `experiments/extension/data/review_v4.md` (lowest plausibility first). No cells run.

## 2026-11-09: Session 6 (cont.): targets v5, truth-blind checks + knowledge probe (paid, ≈ ₹0.75)

### Reason for the change
- The v3/v4 1–5 rater scored **truth, not believability**: it marked down swaps whose true value it knew (e.g. Kamloops → Vancouver, Waseca County → Hennepin County rated 2–3). The kept sample was therefore biased towards facts the model does not know. That would hide any effect of the model's prior at the filter stage (B), which is exactly what the protocol needs to measure. The bar was not lowered; the rubric was replaced.

### Decisions
- **Three truth-blind yes/no checks** in one call (own cache `outputs/extension/target_checks_v5/llm_cache`), explicitly told to ignore the true value: TYPE (same fine-grained type as o), COHERENT (grammatical and coherent), POSSIBLE (no impossibility a reader who doesn't know the fact would spot). Keep iff all three are yes.
- **Closed-book knowledge probe** per target (separate call, own cache `outputs/extension/knowledge_probe_v5/llm_cache`): (s, r, ?) with no context. `model_knows_o` = normalized answer equals o / an alias, or contains it as a whole phrase (`model_knows_o_exact` = equality only). It is a covariate, not a filter. `analysis.py` splits on it only where each bin has ≥ 15 swaps.
- Everything else unchanged: v4's generated o′ (no regeneration), one question per gold passage, the offline checks, frequency logging, cap 120, collision groups recomputed.

### Run (code at `b4c23b2`, tree clean)
- Log: `logs/targets_v5_20261109_021859.log`; per-swap checks and probe answers: `outputs/extension/target_checks_v5/checks_and_probe.json`.
- Estimate (upper bound) ₹0.95. Actual: 132 check + 132 probe calls, 42,015 in / 2,444 out tokens, ≈ **₹0.75** at list × 1.1.
- Funnel: 139 distinct passages → 132 with a generated o′ passing the offline checks (v4) → **125 all three yes** (TYPE no: 6, POSSIBLE no: 1, COHERENT no: 0) → **120 after the cap** (5 removed by the seeded cap).
- **Yield: 120 distinct swaps in 2 collision groups (115 + 5).**
- **model_knows_o: yes 32 / no 88** among the kept (exact match only: 28 yes). Over all 132 candidates: 34 / 98. So the split is used (both bins ≥ 15).
- Frequency: o′ absent 62 / 1–9 41 / ≥ 10 17 (o′ split used); o 1–9 106 / ≥ 10 14 (o split not used, since its 2–9 and ≥ 10 bins fall short).
- Caveats: the checks now reject very little (7 of 132), so the hand review in `review_v5.md` is the effective quality filter. The probe uses the bare triple subject, which is sometimes underspecified (e.g. "13th Legislative District"), so `model_knows_o` = no includes some cases where the question is just ambiguous.
- Written: `experiments/extension/data/targets_v5.jsonl`, `experiments/extension/data/review_v5.md` (kept and dropped tables with the three checks, model_knows_o and the probe answer per swap). Defaults still point to v1. No cells run.

## 2026-11-09: Session 6 (cont.): titled knowledge re-probe; hand-review tooling (paid, ≈ ₹0.16)

- **Why:** the bare probe (subject + relation) was sometimes underspecified (e.g. "13th Legislative District" without the state).
- **Re-probe:** gold passage title + subject + relation, no passage text and no answer. Fresh cache: `outputs/extension/knowledge_probe_v5_titled/llm_cache`. `model_knows_o` is now set from this probe. The bare probe is kept per target as `probe_answer_bare` / `model_knows_o_bare`. Same 120 swaps and groups (each rebuilt swap is checked against `targets_v5.jsonl`). Code: `experiments/extension/reprobe_v5.py`.
- Run at `293125a` (tree clean); log `logs/reprobe_v5_20261109_030419.log`; per-target answers `outputs/extension/knowledge_probe_v5_titled/probe_titled.json`. Estimate (upper) ₹0.31; actual 132 calls, 8,823 in / 493 out tokens, ≈ **₹0.16**.
- **model_knows_o (titled), 120 kept: yes 48 / no 72** (exact match only: 46 / 74). Bare probe before: 32 / 88. Transitions bare → titled: no→no 66, no→yes 22, yes→no 6, yes→yes 26. Over all 132: 52 / 80.
- Cross-tab o′ frequency × knows o: absent 35 no / 27 yes; 1–9 28 / 13; ≥ 10 9 / 8. With the default all-y marks, both the o′-frequency and model_knows_o splits pass the ≥ 15 rule; o frequency does not.
- **Hand review tooling:** `review_v5.md` now has a `keep` column (default `y`) and shows both probe answers. `experiments/extension/finalize_targets.py` reads the marks (must be y/n for exactly the 120 targets), writes `data/targets_final.jsonl` keeping the collision groups, and prints counts per o′-frequency bin and model_knows_o plus which analysis splits would be used. Tested; run end to end on the default marks into the scratchpad only. `targets_final.jsonl` not written yet; waiting for the hand marks.
- Session spend so far (estimates at list × 1.1): picker v2 ₹1.40, plausibility v3 ₹0.31, v4 ₹0.98, v5 ₹0.75, re-probe ₹0.16, total ≈ **₹3.60**. Key usage not checked.
