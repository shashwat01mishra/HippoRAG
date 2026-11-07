# HippoRAG 2 reproduction + contradiction-aware updating (CS F429)

## Project
- Base paper: HippoRAG 2, "From RAG to Memory: Non-Parametric Continual Learning for LLMs" (ICML 2025, arXiv 2502.14802).
- Reproduction target: MuSiQue (1,000 queries, 11,656 passages). Metrics: passage Recall@5 and QA token F1.
- Models: gpt-4o-mini (LLM) and text-embedding-3-small (embedder), instead of the paper's Llama-3.3-70B and NV-Embed-v2.
- What gets reproduced is the gap between HippoRAG 2 and dense retrieval using the same embedder, not the absolute numbers. The paper's gap: Recall@5 74.7 vs 69.7, F1 48.6 vs 45.7. F1 with a gpt-4o-mini reader is compared against the paper's Appendix C Table 8.
- Solo project.
- Platform is now a MacBook Pro M5 (macOS, Apple Silicon). The WSL notes in PROGRESS.md are historical.

## Scope (revised 23 Oct, after Presentation 1)
Claim: a theory of when retrieval memory resists correction, a protocol that measures it,
and evidence across three kinds of memory. Not claimed as novel: contradiction-aware
updating (Zep and Mem0 already do it).

- Floor:
  1. Reproduction: the HippoRAG 2 vs dense gap on MuSiQue.
  2. Theory: per-passage PPR symmetry means resistance comes from seed exclusion,
     top-5 contamination or graph asymmetry. Write the prediction before any run.
  3. Update-resistance protocol: injected counterfactuals; grid of n (old-fact support)
     by k (corrections); metrics correction@5, correction-outranks-old, contamination@5;
     dense and HippoRAG 2 on the same index; every failure attributed to one of the
     three mechanisms. Question: how much graph propagation adds beyond plain redundancy.
  4. Contradiction-aware seeding, tested as one intervention: changed facts improve,
     unchanged facts don't drop.
- Ceiling: long-context reader arm (also locates retriever vs reader failure);
  copies factor (exact copies vs paraphrases).
- Future work: real corrections (TimeQA, Wikidata), Zep-style invalidation,
  belief integrator, small extraction model.
- Cut order if time runs out: copies factor, then long-context arm. Never cut the
  reproduction, the fix or the attribution.

## Deadlines
- Eval 2 (reproduction + enhancement): date not announced, planning for 13 Nov 2026.
- Final IEEE paper: 14 Nov 2026, may move with Eval 2.

## Rules
- `main` stays identical to upstream. Work happens on `dev`.
- Reproduction numbers come from unmodified src/ (tag `upstream-base`). Record the commit hash with every result.
- My own code goes in experiments/. Changes to src/ happen only for the extension, on their own branch, and each one gets explained.
- Ask before any paid API call, and estimate tokens and cost first. Test on a subset before any full run.
- Long runs go in tmux, with output tee'd to logs/.
- Every run gets its own --save_dir.
- Experiments never modify a base index; copy the working dir per experimental condition.
- Offline, network-blocked verification in temp dirs is allowed without asking. Writing anywhere under outputs/ is not.
- Log every session in PROGRESS.md: date, what ran, the numbers, the cost, and any decisions.
- Explain what a command does before running it. I need to understand everything that gets built.
- Write any multi-line text (logs, notes, commit bodies) with the file-write tool, never through shell strings. Commit bodies go in a file passed with `git commit -F`.
