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
