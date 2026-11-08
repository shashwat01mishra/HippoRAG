"""Steps 4-5: retrieval with per-stage attribution, plus the contradiction-aware fix, without editing src/.

AttributionHippoRAG overrides two upstream methods and adds one per-query driver:
  rerank_facts  -> calls upstream unchanged, records stage A (candidates + scores) and stage B (kept facts);
                   with apply_fix=True it then drops superseded facts (step 5).
  run_ppr       -> calls upstream unchanged, records the reset vector (stage C) and passage scores (stage D).
  trace_query   -> the body of upstream retrieve()'s per-query loop for one query (fact scores -> rerank_facts
                   -> dense fallback or graph_search_with_fact_entities), returning the ranking plus the trace.
                   tests/ check that its ranking equals upstream retrieve() on the synthetic corpus.
The dense arm uses dense_passage_retrieval on the same object, so it ranks the same passage vectors and the
same frozen query vector as the graph arm.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import text_processing  # noqa: E402
from src.hipporag.HippoRAG import HippoRAG  # noqa: E402
from src.hipporag.embedding_store import compute_mdhash_id  # noqa: E402

DEFAULT_TIE_TOLERANCE = 0.01   # relative; applied at analysis time only (records keep raw scores)
TOP = 5


def canonical_fact_key(subject: str, relation: str):
    """==== CANONICALIZATION HOOK (design decision, deliberately unimplemented) ====

    The fix treats two kept facts as contradicting when they share this key but differ in object.
    For now: exact match on the already-normalized (subject, relation) strings. Replace this function
    with your canonicalization rule (relation synonyms, subject aliasing, ...). Nothing else needs to change.
    """
    return (subject, relation)


def outranks_old(best_new, best_old, tolerance=DEFAULT_TIE_TOLERANCE):
    """'outranks' / 'near_tie' / 'loses', or None when there is no corrected passage (k=0).

    Relative tolerance: near_tie when |new - old| <= tolerance * max(|new|, |old|). Relative, because PPR
    scores (~1e-4) and cosine similarities (~0.5) live on different scales.
    """
    if best_new is None or best_old is None:
        return None
    scale = max(abs(best_new), abs(best_old))
    diff = best_new - best_old
    if scale == 0 or abs(diff) <= tolerance * scale:
        return "near_tie"
    return "outranks" if diff > 0 else "loses"


class AttributionHippoRAG(HippoRAG):
    apply_fix = False
    _trace = None          # set per query by trace_query; overrides record into a scratch dict otherwise

    def _active_trace(self):
        return self._trace if self._trace is not None else {}

    # ---- vectors -----------------------------------------------------------------------------------
    def install_frozen_embedder(self, embedder):
        """Route every embedding request (stores and queries) through a strict lookup embedder."""
        self.embedding_model = embedder
        for store in (self.chunk_embedding_store, self.entity_embedding_store, self.fact_embedding_store):
            store.embedding_model = embedder

    def preload_query_vectors(self, table, queries):
        """Put frozen query vectors in place after prepare_retrieval_objects (which resets the dict)."""
        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        for q in queries:
            vec = np.asarray(table[q], dtype=np.float32)
            self.query_to_embedding["triple"][q] = vec
            self.query_to_embedding["passage"][q] = vec

    # ---- overrides ---------------------------------------------------------------------------------
    def rerank_facts(self, query, query_fact_scores):
        trace = self._active_trace()
        link_top_k = self.global_config.linking_top_k
        if len(query_fact_scores) and len(self.fact_node_keys) and link_top_k > 0:
            if len(query_fact_scores) <= link_top_k:
                cand = np.argsort(query_fact_scores)[::-1].tolist()
            else:
                cand = np.argsort(query_fact_scores)[-link_top_k:][::-1].tolist()   # same as upstream
            rows = self.fact_embedding_store.get_rows([self.fact_node_keys[i] for i in cand])
            trace["stage_a"] = [{"fact": list(eval_fact(rows[self.fact_node_keys[i]]["content"])),
                                 "score": float(query_fact_scores[i])} for i in cand]
        else:
            trace["stage_a"] = []
        indices, facts, log = super().rerank_facts(query, query_fact_scores)
        trace["stage_b"] = {"kept": [list(f) for f in facts], "error": log.get("error")}
        if self.apply_fix:
            indices, facts, dropped = self.drop_superseded(indices, facts)
            trace["fix"] = {"dropped": dropped, "kept": [list(f) for f in facts]}
        return indices, facts, log

    def run_ppr(self, reset_prob, damping=0.5):
        trace = self._active_trace()
        trace["reset"] = np.where(np.isnan(reset_prob) | (reset_prob < 0), 0, reset_prob).copy()
        ids, scores = super().run_ppr(reset_prob, damping)
        trace["ppr"] = (ids, scores)
        return ids, scores

    # ---- step 5: the fix ---------------------------------------------------------------------------
    def fact_recency(self, fact):
        """Most recent insert_seq among the chunks asserting this fact (base corpus = 0)."""
        sources = self.proc_triples_to_docs.get(str(tuple(fact)), set())
        return max((int(self.chunk_metadata.get(cid, {}).get("insert_seq", 0)) for cid in sources), default=0)

    def drop_superseded(self, indices, facts):
        """Among kept facts sharing canonical (subject, relation) with different objects, keep only the newest.

        Facts in a conflicting group whose recency is below the group maximum are dropped; if all have equal
        recency (e.g. two base-corpus facts) nothing is dropped.
        """
        groups = {}
        for pos, fact in enumerate(facts):
            groups.setdefault(canonical_fact_key(fact[0], fact[1]), []).append(pos)
        drop = set()
        for positions in groups.values():
            if len({facts[p][2] for p in positions}) < 2:
                continue
            recency = {p: self.fact_recency(facts[p]) for p in positions}
            newest = max(recency.values())
            drop |= {p for p in positions if recency[p] < newest}
        kept = [p for p in range(len(facts)) if p not in drop]
        dropped = [{"fact": list(facts[p]), "recency": self.fact_recency(facts[p])} for p in sorted(drop)]
        return [indices[p] for p in kept], [facts[p] for p in kept], dropped

    # ---- per-query driver --------------------------------------------------------------------------
    def trace_query(self, query):
        """Upstream retrieve()'s per-query loop for one query, with the trace kept."""
        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        self.get_query_embeddings([query])
        self._trace = {}
        fact_scores = self.get_fact_scores(query)
        indices, facts, _log = self.rerank_facts(query, fact_scores)
        if len(facts) == 0:
            self._trace["fallback_dense"] = True
            ids, scores = self.dense_passage_retrieval(query)
        else:
            self._trace["fallback_dense"] = False
            ids, scores = self.graph_search_with_fact_entities(
                query=query, link_top_k=self.global_config.linking_top_k, query_fact_scores=fact_scores,
                top_k_facts=facts, top_k_fact_indices=indices, passage_node_weight=self.global_config.passage_node_weight)
        trace, self._trace = self._trace, None
        return np.asarray(ids), np.asarray(scores), trace

    # ---- attribution record ------------------------------------------------------------------------
    def attribute(self, target, old_ids, new_ids, gold_other_ids=(), injected_ids=()):
        """One record per (question, cell): HippoRAG stages A-E, dense arm, metrics.

        old_ids: the base gold chunk plus the cell's extra old copies; new_ids: the cell's corrections;
        gold_other_ids: the question's other supporting passages; injected_ids: all injected chunks in the cell.
        """
        query = target["question"]
        ids, scores, trace = self.trace_query(query)
        key_to_row = {k: i for i, k in enumerate(self.passage_node_keys)}
        q_vec = self.query_to_embedding["passage"][query]
        cosine = {cid: float(np.dot(self.passage_embeddings[key_to_row[cid]], q_vec)) for cid in list(old_ids) + list(new_ids)}

        def role(cid):
            if cid in old_ids:
                return "old"
            if cid in new_ids:
                return "new"
            if cid in gold_other_ids:
                return "gold_other"
            if cid in injected_ids:
                return "other_injected"
            return "other"

        def arm(order_rows, order_scores, score_of):
            keys = [self.passage_node_keys[r] for r in order_rows]
            rank = {k: i + 1 for i, k in enumerate(keys)}
            top = keys[:TOP]
            best_old = max((score_of[c] for c in old_ids), default=None)
            best_new = max((score_of[c] for c in new_ids), default=None)
            return {
                "top5": [{"chunk": k, "role": role(k), "score": float(s)} for k, s in zip(top, order_scores[:TOP])],
                "passages": {c: {"role": role(c), "rank": rank[c], "score": score_of[c], "cosine": cosine[c]}
                             for c in list(old_ids) + list(new_ids)},
                "correction_at5": any(c in new_ids for c in top) if new_ids else None,
                "contamination_at5": sum(1 for c in top if c in old_ids),
                "best_old": best_old, "best_new": best_new,
                "margin_old_minus_new": None if best_new is None else best_old - best_new,
            }

        hippo_score = {self.passage_node_keys[r]: float(s) for r, s in zip(ids, scores)}
        record = {"target_id": target["target_id"], "question": query, "fix": self.apply_fix,
                  "stage_a": trace["stage_a"], "stage_b": trace["stage_b"], "fallback_dense": trace["fallback_dense"]}
        if self.apply_fix:
            record["fix_trace"] = trace.get("fix")
        new_fact = [text_processing(target["s"]), text_processing(target["r"]), text_processing(target["o_prime"])]
        old_fact = [text_processing(target["s"]), text_processing(target["r"]), text_processing(target["o"])]
        record["flags"] = {
            "old_fact_in_candidates": any(f["fact"] == old_fact for f in trace["stage_a"]),
            "new_fact_in_candidates": any(f["fact"] == new_fact for f in trace["stage_a"]),
            "old_fact_kept": old_fact in trace["stage_b"]["kept"],
            "new_fact_kept": new_fact in trace["stage_b"]["kept"],
        }
        if not trace["fallback_dense"]:
            reset = trace["reset"]
            total = float(reset.sum())
            seeds = {}
            for name in ("s", "o", "o_prime"):
                key = compute_mdhash_id(text_processing(target[name]), prefix="entity-")
                v = self.node_name_to_vertex_idx.get(key)
                seeds[name] = None if v is None else float(reset[v])
            for c in list(old_ids) + list(new_ids):
                seeds[c] = float(reset[self.node_name_to_vertex_idx[c]])
            phrase_mass = float(reset[self.entity_node_idxs].sum())
            record["stage_c"] = {"seeds": seeds, "reset_total": total, "phrase_mass": phrase_mass,
                                 "passage_mass": total - phrase_mass,
                                 "n_phrase_seeds": int((reset[self.entity_node_idxs] > 0).sum())}
        else:
            record["stage_c"] = None
        record["hipporag"] = arm(ids, scores, hippo_score)        # stage D (passages/margin) + stage E (top5)
        d_ids, d_scores = self.dense_passage_retrieval(query)
        dense_cos = {c: cosine[c] for c in cosine}
        dense_arm = arm(d_ids, d_scores, dense_cos)               # outranks on raw cosine, ranks on dense order
        record["dense"] = dense_arm                               # best_new/best_old are raw cosines
        return record


def eval_fact(content):
    import ast
    return ast.literal_eval(content)


class FixedHippoRAG(AttributionHippoRAG):
    apply_fix = True
