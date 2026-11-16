# Viva answers

Try `VIVA.md` first. References are `file:line`; `H` = `src/hipporag/HippoRAG.py`. Result sources: R = `results/musique_n500/bootstrap_n500.txt`, S = `analysis/grid_v5_final/summary.md`, U = `analysis/grid_v5_final/followup.md`, B = `analysis/grid_v5_final/bootstrap.csv`, P = `analysis/grid_v5_final/phase_b.md`, M = `analysis/grid_v5_final_minus_specialist/phase_b.md`, T = `paper/sections/reproduction.tex`, Q = `demo/traces/q193.md`, L = `PROGRESS.md`.

## A. The paper

**1.** Index time: an LLM extracts triples from each passage (OpenIE); entities become nodes, triples become entity–entity edges, each passage becomes a node linked to its entities (`H:1179`, `H:1230`), and similar entities get synonym edges (`H:1278`). Query time: embed the query, score it against every triple (`H:1892–1928`), take the top 5 (`H:2151–2156`), let an LLM filter them (`H:2164`), turn the kept triples' entities into seeds, add every passage as a weak seed, run Personalized PageRank (`H:2204–2212`), rank passages by score. Versus HippoRAG 1: passages are nodes in the graph, the query is matched to triples and not to extracted query entities, and there is an LLM filter.

**2.** A triple carries the relation, so the match uses the question's meaning and not just a name. Query NER can miss or mislink entities, and an entity alone says nothing about which fact is wanted.

**3.** Input: the question and the top-5 candidate triples as JSON. Output: the subset the LLM judges relevant (`src/hipporag/rerank.py:102–125`; each returned fact is mapped back to a candidate by closest string match, `rerank.py:118`). If nothing is kept, retrieval falls back to plain dense ranking (`experiments/extension/attrib_rag.py:138–140` mirrors upstream's loop). In my grid the fallback happened for 2 of 75 questions (P, funnel).

**4.** Passage seeds let dense similarity contribute and make sure a relevant passage with no linked entity can still score. The weight is small so entity seeds, concentrated on a few nodes, are not drowned. Default 0.05 (`src/hipporag/utils/config_utils.py:91–94`); applied at `H:2093–2099`. Even so, passages hold 98.0 % of the reset mass in my demo trace because there are 11,655 of them (Q).

**5.** It adds new passages and checks that performance on existing questions holds, i.e. growth. It does not test a fact that changes while the old passage stays indexed. (Confirm the section number in the paper; the "6.3" on my slide is from my notes.)

**6.** Absolute scores (mine are lower: 62.0 vs 74.2 Recall@5; R, T). Filter behaviour, since it is a prompted LLM judgement and the shipped prompt was tuned for Llama-3.3 (`experiments/run_subset.py:130`). Triple quality, which sets the graph. What did transfer: the gap over dense.

## B. PageRank maths

**7.** π = (1 − d)·r + d·Wᵀπ, with W the row-normalised weighted adjacency matrix. r is where the walk restarts; d is the probability of following an edge and not restarting. igraph's `damping` is that d (`H:2204–2212`). HippoRAG 2 uses 0.5 (`config_utils.py:192–195`).

**8.** d/(1 − d): 1 step at 0.5; 0.85/0.15 ≈ 5.7 steps at 0.85. At 0.5 relevance stays within about one hop of the seeds, which suits a passage–entity–passage pattern. At 0.85 mass drifts to wherever the graph is densest.

**9.** `directed=False` (`H:2208`): mass flows both ways along every edge, so hubs collect it from everywhere. "united states" has degree 1,906, the highest of any entity (`demo/graph_stats.md`, max entity degree; node identity checked in the graph pickle) and appears in the PPR top 10 of both demo traces (Q, `demo/traces/q96.md`).

**10.** To down-weight entities that occur in many passages, like an inverse document frequency: `H:2064–2065`. In Q193 "diana degarmo" (5 passages) gets 0.18 while "season three runner up" (1 passage) gets 0.91 (Q).

**11.** By symmetry. Mass leaves the subject along its passage edges in proportion to edge weight, and every passage, old or new, hangs off the subject the same way. Old-object and new-object nodes only pass mass back among their own passages. Result: d/((1+d)(n+k)) for each passage (`paper/sections/theory.tex`, Prop. 1; verified by `experiments/theory/verify_margin.py`, L Session 7).

**12.** The 98 % is spread over 11,655 passages, about 0.0084 % each; the 2 % sits on 4 entities, about 0.5 % each (Q, section 3). Per node, entity seeds are far heavier, so they and their neighbours lead.

## C. The reproduction

**13.** The target stated in `CLAUDE.md` is the gap over dense with the same embedder. Mine: +5.90 Recall@5 [+3.73, +8.00], +4.66 F1 [+1.52, +7.69] (R). The paper's gpt-4o-mini gaps, +4.5 and +3.3 (T, its App. C Tables 8–9), fall inside both intervals. Absolute numbers depend on the embedder, which I changed.

**14.** The dense run reuses HippoRAG's own passage vectors, copied sha256-identical (`experiments/share_chunks_to_dense.py`; L Session 4). Same vectors, same query embedding model; only the graph differs.

**15.** Resample questions with replacement and apply the same resample to both systems, then take the mean difference (`experiments/bootstrap_gap.py:65–66`). Paired because both systems answer the same questions, so question difficulty cancels. Unpaired resampling would add between-question variance and widen the interval.

**16.** The questions are the authors' own 1,000-question sample in file order, so the first 500 is a fixed slice, not a choice made after seeing results. It limits precision, not validity: the CI reflects 500. The remaining 500 would cost about ₹48 (L Session 4), over budget.

**17.** I trust that the shipped gpt-4o-mini extractions came from the current prompt. The model snapshot matches; the prompt cannot be verified (L Session 1, stamp caveat; `experiments/stamp_openie_cache.py`). If the prompt differed, my graph differs from what a fresh run would build. One visible oddity: 2,457 of 11,656 docs list NER entities that do not belong to their triples; it is harmless because nodes come from triples only (`H:564`).

**18.** Query embeddings are re-fetched and are not bit-identical; 2 of 400 questions got a different top 5 (L Session 4). The extension embeds every text once and serves it from a frozen table that raises on anything unknown (`experiments/extension/vectors.py:33`).

## D. The extension

**19.** Adding two stale copies of the old passage costs HippoRAG 2 11.7 points of correction@5 [−17.0, −6.7] and dense 0.7; the interaction is −11.0 points [−16.7, −6.0] (U §1). Overall the two are level: 41.5 % vs 39.0 %, +2.5 pts [−6.7, +11.3] (P).

**20.** Nothing the filter does: it kept 8 of the 9 corrections it saw (P). And I should not say "the candidate step is the bottleneck" either. The correction's fact is among the 5 candidate triples for 9 of 75 questions, but so is the old fact before any correction: 9 of 75 at k = 0 (U §2). For multi-hop questions the last-hop fact is rarely seeded at all; passages mostly reach the top 5 through their own passage seed and graph spread (of 249 retrieved corrections, 71 had a candidate fact, 114 were also in the dense top 5, 64 were lifted by the graph; U §2). What actually separates the systems is repetition: two extra old copies cost HippoRAG 2 11.7 points and dense 0.7, interaction −11.0 [−16.7, −6.0] (U §1). I got it wrong because I reasoned about the filter's judgement and never checked how often the last-hop fact reaches it. The baseline and route numbers are exploratory.

**21.** `first_failure` returns the first stage whose test fails (`experiments/extension/analysis.py:56–68`), and "not a candidate" is tested first, so it absorbs every failure: 36–49 of 75 per cell (S). But the same label fits most successes too: 178 of the 249 retrieved corrections were not candidates (U §2), and the old fact is not a candidate for 66 of 75 at k = 0. So stage A is the normal route, not a failure mode. The second effect is repetition. In the 35 records HippoRAG 2 retrieves at n = 1 and loses at n = 3, the old passage outranks the correction in 27; an old copy is in the top 5 in 19, and the correction then sits at rank 6–10 in all 19 (U §3). The order follows dense similarity (ρ = +0.91), not node degree (ρ = +0.14, p = 0.43) (U §3). Dense is protected because its ranks move by at most 2 when copies are added (0 of 118 move 3 or more; it loses 2 of 118), while 30 of HippoRAG 2's 142 move 3 or more and it loses corrections that were at rank 2 or 3 (U §4). All of this is exploratory.

**22.** No, but it acts at the seed stage, and most corrections do not arrive through seeded facts (178 of 249; U §2). Where it fires (7 questions) it removes the old seed in 7 of 7 and makes the correction outrank the old passage in 7 of 7 (P). It lowers stale passages in the top 5 at k = 5: 0.61 → 0.41 at n = 3, [−0.40, −0.04] (B). It drops no unrelated fact (S). correction@5 barely moves because those 7 already succeeded.

**23.** The fix calls two kept facts contradictory when subject and relation strings match exactly (`experiments/extension/attrib_rag.py:27–34`, `:109–127`). My corrections copy the old triple with only the object changed, so detection is perfect by construction. Real corrections paraphrase relations and alias entities, so recall would drop; and multi-valued relations would give false positives.

**24.** Only by insertion order, stored in chunk metadata and used by the fix alone (`attrib_rag.py:104–107`). PPR and the reader cannot see it. So the long-context reader choosing the old value (41 of 75 at (1,1); P) is not an error on its part; it has no cue. That is a limitation of the protocol, stated in `RESULTS_BRIEF.md` §6.

**25.** The marks were set before any result was opened (commits `927d6fe` and `6c56e00` precede the first analysis; the seal check came after). The criteria concern the swap text only. The run used all 120, so nothing was rerun. And the conclusions hold on a different subset: without the 8 borderline rows, −0.7 pts [−9.9, +8.6] and the same stale-copy penalty (M).

## E. The code

**26.** By subclassing. `AttributionHippoRAG` overrides `rerank_facts` and `run_ppr`, records their inputs and outputs, and calls `super()` unchanged (`attrib_rag.py:76–101`). `git diff --stat upstream-base -- src main.py` is empty; every launcher logs it (`experiments/launch_run.zsh:11`).

**27.** A unit test compares `trace_query` with upstream `retrieve()` (`experiments/extension/tests/test_extension.py:253–260`), and every grid cell re-checked it on 5 random questions as a gate (`experiments/extension/run_cells.py:306–313`). The demo also asserts that its all-node PPR equals upstream's passage scores (`demo/demo_lib.py`, `trace_question`).

**28.** Observed (L, Session 8 cont.; `logs/demo_live_viva_*.log`): "united states" moves to rank 1; the four seed entities stay in the top 5; one gold passage drops out (a Diana DeGarmo album passage enters) and Recall@5 goes 1.00 → 0.50. Reason: a longer walk (≈ 5.7 steps) carries mass to hubs and to passages near the seed entities.

**29.** Observed: phrases become 100 % of the reset mass. The top 5 keeps the same five passages, with ranks 3 and 4 swapped; Recall@5 stays 0.50. Reason: at weight 0.05 the passage seeds were already a minor influence per node; the entity seeds decide.

**30.** Observed: no. Hubs take ranks 1–7 (united states, canada, australia, ...); the seed entities fall to ranks 8 and 10; two more "American Idol" passages from the dense top 5 enter the top 5, and Recall@5 goes 1.00 → 0.50. Reason: passage mass is now 99.8 % of the reset, ten times heavier per passage, so the walk starts almost everywhere.

## F. "Did you write this?"

**31.** Be exact. Mine: the question (correction, not growth), the scope after Presentation 1, the three-mechanism theory, the grid design, the blind protocol, the choice of account for the prediction ("the filter is the bottleneck") and every pick in it, the decision rules for screening, every go/no-go on paid runs. Written with Claude Code: the harness code, the analysis scripts, the swap screening pass, the deck and these files. The prediction file says so in its first line (`notes/prediction.md`). I can explain every script (`CODE_MAP.md`).

**32.** (`attrib_rag.py:109–127`.) Group the kept facts by `canonical_fact_key(subject, relation)`. Skip groups whose facts all share one object: no conflict. For a conflicting group, look up each fact's recency, the largest `insert_seq` among the passages asserting it (`fact_recency`, `:104–107`; base corpus = 0). Mark every fact older than the newest for dropping. If all are equally recent, drop nothing. Return the surviving indices and facts, plus a log of what was dropped.

**33.** Do not trust it blindly; check it. Every row has a written reason (`experiments/extension/data/review_reasons.md`), 10 rows were drawn at random for a spot check, a second pass disagreed on 2 of 120, and an integrity check found 0 swaps that change anything but o → o′. The result does not depend on the borderline calls (M).

**34.** Offline and free:
`.venv/bin/python experiments/bootstrap_gap.py --hipporag results/musique_n500/hipporag_per_query_n500.json --dense results/musique_n500/dense_per_query_n500.json --first 500`;
`.venv/bin/python experiments/extension/analysis.py --results results/extension/grid_v5_20261109 --targets experiments/extension/data/targets_v5.jsonl --final experiments/extension/data/targets_final.jsonl --out analysis/grid_v5_final`;
`.venv/bin/python experiments/extension/phase_b.py --out analysis/grid_v5_final` (and again with `--out analysis/grid_v5_final_minus_specialist --drop_rows 19,25,29,45,91,100,109,114`);
`.venv/bin/python deck/make_figs.py`.
The traces need the index clone and one query embedding each: `demo/run_demo.py --make_index`, then `--live --save --q 193` and `--q 96`, about ₹0.00 (L Session 8). The per-query and grid records themselves are in `results/`, so nothing paid is needed.
