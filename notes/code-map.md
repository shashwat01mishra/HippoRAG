# HippoRAG 2 code map

Upstream commit `d5c8329` (tag `upstream-base`), package version 2.0.0a5. Paths are relative to `src/hipporag/`. Line numbers are for that commit.

## 1. Knowledge-graph construction from OpenIE output

**Entry point: `HippoRAG.index()`, `HippoRAG.py:499-593`.** Passages are inserted into `chunk_embedding_store`. OpenIE triples are loaded or extracted (`load_existing_openie`, `:544`) and normalized with `text_processing` (`:563`, `utils/misc_utils.py:91`). Subjects and objects become the phrase-node list (`extract_entity_nodes`, `:564`), and triples become the fact list (`flatten_facts`, `:565`). Entities and facts are embedded into their own stores (`:569`, `:572`). The graph is then assembled through `add_fact_edges`, `add_passage_edges`, `add_synonymy_edges` and `augment_graph` (`:582-591`), and pickled to `<working_dir>/graph.pickle` (`save_igraph`, `:1679`).

- **Phrase and passage nodes: `add_new_nodes()`, `HippoRAG.py:1521-1549`.** Every ID in `entity_embedding_store` (keys `entity-<md5>`) and `chunk_embedding_store` (keys `chunk-<md5>`) not already present is added as an igraph vertex, with its `name` set to that ID.
- **Relation (fact) edges: `add_fact_edges()`, `HippoRAG.py:1179-1228`.** For each triple in a chunk that isn't yet in the graph, it records a subject↔object edge. Because the graph is undirected by default, this is one sorted pair. Each occurrence adds +1 to `node_to_node_stats`, and the source chunk is tracked in `_fact_edge_source_counts`. The predicate is not stored on the edge. The method also fills `ent_node_to_chunk_ids`, which maps each entity to the chunks it appears in.
- **"Contains" (passage→phrase) edges: `add_passage_edges()`, `HippoRAG.py:1230-1276`.** Each new chunk gets an edge `(chunk_key, entity_key)` of weight 1.0 to every entity in its triples, with the source recorded in `_passage_edge_sources`. It returns the number of new chunks.
- **Synonym edges: `add_synonymy_edges()`, `HippoRAG.py:1278-1353`.** See section 2.
- **Edge merge: `add_new_edges()`, `HippoRAG.py:1551-1677`.** It merges this pass's contributions with existing edges by logical key, so no parallel edges are created. Edge `weight` = max(sum of fact source counts, 1.0 if it is a passage edge, synonym score) (`:1589`). `edge_kind` is a `+`-joined string of `fact`, `passage` and `synonym`.

## 2. Synonym edges

**`add_synonymy_edges()`, `HippoRAG.py:1278-1353`, with KNN in `retrieve_knn()`, `utils/embed_utils.py:6`.** It runs a cosine KNN (torch matmul over L2-normalized embeddings, `k=synonymy_edge_topk=2047`) from query phrase nodes against **all** phrase nodes. For each query entity with more than 2 alphanumeric characters, it walks the neighbours in score order and stops at the first score below `synonymy_edge_sim_threshold` (**0.8**, `utils/config_utils.py:172`) or after 100 neighbours (`:1338`). Each surviving neighbour gets an edge with weight = the similarity score.

**On an incremental insert, synonym edges are not recomputed across the whole graph.** `index()` sets `_pending_synonymy_entity_ids = new_entity_ids` when a graph already exists (`HippoRAG.py:587`). `add_synonymy_edges` then uses only those new entities as KNN queries (`:1301-1307`; comment at `:1316`), while the keys are still all entities. Edges between pairs of pre-existing entities are left as they were. On the first index (no graph yet) the value is `None`, so every entity is used as a query.

## 3. Query-to-triple retrieval and the recognition-memory filter

- **Scoring: `get_fact_scores()`, `HippoRAG.py:1892-1928`.** It takes the dot product of the query embedding (instruction `query_to_fact`) with all fact embeddings, then min-max normalizes.
- **Candidates and filter: `rerank_facts()`, `HippoRAG.py:2124-2175`.** It takes the top `linking_top_k` facts by score (**5** by default; `main.py` also sets 5) as candidates (`:2151-2156`), then calls the filter at **`HippoRAG.py:2164`**: `self.rerank_filter(query, candidate_facts, candidate_fact_indices, len_after_rerank=link_top_k)`. Any exception returns an empty list.
- **Filter: `DSPyFilter.rerank()`, `rerank.py:103-126`.** It makes one LLM call (`llm_call`, `rerank.py:~80-98`, using `hipporag.extraction_llm.infer`) with a DSPy-derived prompt. The prompt template comes from `rerank_dspy_file_path`; `main.py` points this at `filter_llama3.3-70B-Instruct.json`. The output facts are mapped back to candidates with `difflib.get_close_matches` (cutoff 0.0). The result is capped at `len_after_rerank`.
- **Fallback: `retrieve()`, `HippoRAG.py:762-764`.** If no facts survive the filter, the query uses plain dense passage retrieval (`dense_passage_retrieval`, `:1930`) instead of PPR.

## 4. Reset probabilities (PPR seeds)

**`graph_search_with_fact_entities()`, `HippoRAG.py:2008-2121`.**
- **Phrase nodes (`:2047-2072`).** For every subject and object of each filtered fact that is a graph node, the fact's normalized score divided by the number of chunks that contain the entity (`len(ent_node_to_chunk_ids[phrase_key])`, `:2064-2065`) is added. The sum is then divided by the number of times the phrase occurred across facts (`:2072`). `get_top_k_weights()` (`:1970-2006`, called at `:2085`) zeros every phrase weight outside the top `link_top_k` phrases.
- **Passage nodes (`:2090-2099`).** Every passage gets its min-max-normalized dense-retrieval score × `passage_node_weight` (**0.05**, `utils/config_utils.py:91`, passed in at `:771`).
- **Combination (`:2102`).** `node_weights = phrase_weights + passage_weights` is passed as the reset vector. If it sums to ≤ 0, a `StateConsistencyError` is raised (`:2108-2109`).

## 5. Personalized PageRank

**`run_ppr()`, `HippoRAG.py:2177-2218`.** It calls **python-igraph** `Graph.personalized_pagerank(vertices=all, damping=damping, directed=False, weights='weight', reset=reset_prob, implementation='prpack')` (`:2204-2212`). NaN or negative resets are first zeroed (`:2203`). Passage-node scores are extracted and sorted descending (`:2214-2216`).
- **Damping is 0.5.** The default is `BaseConfig.damping`, `utils/config_utils.py:192-195`. It is passed at `HippoRAG.py:2113` (`damping=self.global_config.damping`). `run_ppr` also has its own default of 0.5 and falls back to 0.5 if passed `None` (`:2179`, `:2202`). `main.py` does not override it.

## 6. Incremental `index()` and `delete()`

- **Second `index()` call (`HippoRAG.py:499-593`).** New passages are inserted into the chunk store, and duplicates are skipped by hash ID. `load_existing_openie` (`:1354-1404`) returns the chunk IDs that are not yet in the stored OpenIE state, and only those are sent to OpenIE (`:548-550`); the merged state is then saved (`:553`). Fact and passage edges are added only for chunks not already in the graph (`chunk_key not in current_graph_nodes`, `:1220`, `:1266`). Synonym KNN runs only for newly added entity IDs (section 2). `add_new_edges` merges into existing edges by logical key, and the graph is re-saved. If the new docs add no new chunks (`num_new_chunks == 0`), the graph isn't touched (`:585`). Appending OpenIE rows produced by a different LLM/producer raises an error (`:1400-1401`).
- **`delete(docs_to_delete)` (`HippoRAG.py:595-682`).** It only considers docs present in the chunk store, matched on exact text. It removes the deleted chunks' triples from `proc_triples_to_docs`. Facts and entities are deleted only when no remaining chunk references them (`:641-661`; the docstring says shared triples and entities are kept). It rewrites the OpenIE state without the deleted chunks (`:667`) and deletes entries from the entity, fact and chunk stores and chunk metadata (`:670-675`). `_remove_fact_sources_from_graph` (`:684-702`) strips the deleted chunks from each edge's `fact_source_counts`. It deletes an edge if nothing remains and it has no synonym score; otherwise it recomputes the weight. Finally it deletes the unreferenced entity vertices and the chunk vertices, which also removes their incident edges (`:679`), and re-saves the graph.

## 7. Metrics

- **Recall@k: `RetrievalRecall.calculate_metric_scores()`, `evaluation/retrieval_eval.py:24`, loop at `:53-60`.** Per query it computes |set(top-k retrieved passage strings) ∩ set(gold passage strings)| / |set(gold)|, averaged over queries. It is called from `HippoRAG.retrieve()` at `HippoRAG.py:788-789` with `k_list=[1,2,5,10,20,30,50,100,150,200]`. Gold passages are built in `main.py:get_gold_docs` as `title + "\n" + text` of supporting paragraphs. `StandardRAG.retrieve()` (`StandardRAG.py:214`) uses the same evaluator.
- **F1: `QAF1Score.calculate_metric_scores()`, `evaluation/qa_eval.py:56-96`.** Token-level F1 between `normalize_answer`-ed (`utils/eval_utils.py:4`) gold and predicted answers. The max over gold aliases is taken (`aggregation_fn=np.max`), then the result is averaged over queries. It is called from `HippoRAG.rag_qa()` at `HippoRAG.py:929` / `:948`, and exact match comes from `QAExactMatch` in the same file. The QA reader sees the top `qa_top_k` passages (`HippoRAG.py:1141`).

## Retrieval-relevant defaults in `utils/config_utils.py`

| Field | Default | Line | Effect |
|---|---|---|---|
| `retrieval_top_k` | 200 | 188 | passages returned per query and evaluated for Recall@k |
| `linking_top_k` | 5 | 184 | facts sent to the filter, facts kept after it, and phrase seeds kept |
| `qa_top_k` | 5 | 203 | passages given to the QA reader |
| `damping` | 0.5 | 192 | PPR damping |
| `passage_node_weight` | 0.05 | 91 | multiplier on passage-node dense scores in the reset vector |
| `synonymy_edge_sim_threshold` | 0.8 | 172 | minimum cosine similarity for a synonym edge |
| `synonymy_edge_topk` | 2047 | 160 | KNN neighbours considered per phrase (also capped at 100 accepted, hard-coded at `HippoRAG.py:1338`) |
| `is_directed_graph` | False | 176 | undirected graph (PPR also runs with `directed=False`) |
| `max_qa_steps` | 1 | 199 | one retrieve-then-read step |
| `embedding_return_as_normalized` | True | 144 | embeddings L2-normalized (dot product = cosine) |
| `temperature` | 0 | 50 | used for OpenIE, the filter and QA |

`main.py` explicitly sets `retrieval_top_k=200`, `linking_top_k=5` and `qa_top_k=5`, which are the same as the defaults.
