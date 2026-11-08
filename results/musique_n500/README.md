# MuSiQue, first 500 questions: HippoRAG 2 vs dense

Evidence for the n=500 reproduction run (PROGRESS.md, 2026-11-08, Session 4 cont.).

- Code: `abac2cd` (`src/` and `main.py` identical to `upstream-base`), via `experiments/run_subset.py --num_queries 500`.
- Models: gpt-4o-mini + text-embedding-3-small through the AICredits gateway; dense reuses HippoRAG's passage vectors.
- Questions: the first 500 of the authors' 1,000-question sample (`reproduce/dataset/musique.json`, file order).

| File | What | sha256 (first 16) |
|---|---|---|
| `hipporag_per_query_n500.json` | copy of `outputs/hipporag_n500_musique/per_query_n500.json` | `0b363b17ca7239a8` |
| `dense_per_query_n500.json` | copy of `outputs/dense_n500_musique/per_query_n500.json` | `184bca0abdf7eec4` |
| `bootstrap_n100.txt`, `bootstrap_n500.txt` | `experiments/bootstrap_gap.py` output on these copies (command on line 1) | |

Each per-query row: `index`, `question`, `answer`, top-5 `docs` and `doc_scores`, `gold_answers`, `gold_docs`, `doc_metadata`, `graph_seeds`.

Caveat: the n=100 CIs come from the first 100 questions of these runs. Questions 7 and 11 got new HippoRAG answers relative to the original n=100 run (cache misses), so HippoRAG F1 on that slice is 48.15, not the 48.48 logged for the n=100 run.

Reproduce the CIs offline: `.venv/bin/python experiments/bootstrap_gap.py --hipporag results/musique_n500/hipporag_per_query_n500.json --dense results/musique_n500/dense_per_query_n500.json --first 500`
