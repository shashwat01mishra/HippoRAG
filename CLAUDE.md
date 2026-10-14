# HippoRAG 2 reproduction + contradiction-aware updating (CS F429)

## Project
- Base paper: HippoRAG 2, "From RAG to Memory: Non-Parametric Continual Learning for LLMs" (ICML 2025, arXiv 2502.14802).
- Reproduction target: MuSiQue (1,000 queries, 11,656 passages). Metrics: passage Recall@5 and QA token F1.
- Models: gpt-4o-mini (LLM) and text-embedding-3-small (embedder), instead of the paper's Llama-3.3-70B and NV-Embed-v2.
- What gets reproduced is the gap between HippoRAG 2 and dense retrieval using the same embedder, not the absolute numbers. The paper's gap: Recall@5 74.7 vs 69.7, F1 48.6 vs 45.7. F1 with a gpt-4o-mini reader is compared against the paper's Appendix C Table 8.
- Solo project.

## Scope: floor and ceiling
- Floor (graded, must finish): the reproduction plus contradiction-aware graph updating.
  - Detect conflicting triples, mark the old edge as superseded or down-weight it in PPR, and favour the newer passage.
  - Evaluate on injected fact updates: accuracy on changed facts (should improve) and on unchanged facts (must not get worse).
- Ceiling, built in layers:
  1. Entrenchment curve: how many contradicting insertions it takes to flip retrieval, against the fact's graph topology.
  2. Dense-RAG control.
  3. Intervention using the contradiction detector.
  4. Nonlinear belief integrator (post-course).
  5. Robustness with a small extraction model.

## Deadlines
- Eval 1, literature report: around 17 Oct 2026
- Eval 2, reproduction + enhancement: 31 Oct 2026
- Final IEEE paper: 14 Nov 2026

## Rules
- `main` stays identical to upstream. Work happens on `dev`.
- Reproduction numbers come from unmodified src/ (tag `upstream-base`). Record the commit hash with every result.
- My own code goes in experiments/. Changes to src/ happen only for the extension, on their own branch, and each one gets explained.
- Ask before any paid API call, and estimate tokens and cost first. Test on a subset before any full run.
- Long runs go in tmux, with output tee'd to logs/.
- Log every session in PROGRESS.md: date, what ran, the numbers, the cost, and any decisions.
- Explain what a command does before running it. I need to understand everything that gets built.
