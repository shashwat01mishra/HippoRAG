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
