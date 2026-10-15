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
