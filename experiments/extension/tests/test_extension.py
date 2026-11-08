"""Offline tests for the extension harness: synthetic corpus, mock LLM, mock embedder, mock OpenIE.

Run from the repo root:  .venv/bin/python -m pytest experiments/extension/tests -q
"""
import hashlib
import json
import re
import socket
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experiments.extension import inject, long_context, select_targets, vectors  # noqa: E402
from experiments.extension.attrib_rag import AttributionHippoRAG, outranks_old  # noqa: E402
from experiments.extension.cell_index import index_cell, prepare_cell  # noqa: E402
from experiments.extension.common import chunk_text, text_processing as tp  # noqa: E402
from src.hipporag.HippoRAG import HippoRAG  # noqa: E402
from src.hipporag.embedding_store import compute_mdhash_id  # noqa: E402
from src.hipporag.utils.config_utils import BaseConfig  # noqa: E402
from src.hipporag.utils.misc_utils import NerRawOutput, TripleRawOutput  # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*a, **k):
        raise RuntimeError("network blocked in tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


# ---------------------------------------------------------------- synthetic corpus ---------------
P = {  # title -> (body, triples)
    "Alpha City": ("Alpha City is located in Beta Province. Gamma Person founded Alpha City in 1901.",
                   [["Alpha City", "is located in", "Beta Province"], ["Gamma Person", "founded", "Alpha City"]]),
    "Gamma Person": ("Gamma Person was a merchant who founded a famous city.",
                     [["Gamma Person", "was", "merchant"]]),
    "Delta Town": ("Delta Town is located in Zeta Province on the coast.",
                   [["Delta Town", "is located in", "Zeta Province"]]),
    "Kappa Village": ("Kappa Village is located in Omega Province near hills.",
                      [["Kappa Village", "is located in", "Omega Province"]]),
    "Lambda Hamlet": ("Lambda Hamlet is located in Sigma Province and grows wheat.",
                      [["Lambda Hamlet", "is located in", "Sigma Province"]]),
    "Theta River": ("Theta River flows through Beta Province into the sea.",
                    [["Theta River", "flows through", "Beta Province"]]),
}
CORPUS = {chunk_text(t, b): tr for t, (b, tr) in P.items()}
DOCS = list(CORPUS)

SAMPLE = {
    "id": "2hop__1_2", "question": "In which province is the city founded by Gamma Person?",
    "answer": "Beta Province", "answer_aliases": [], "answerable": True,
    "question_decomposition": [{"id": 1, "question": "q1", "answer": "Alpha City", "paragraph_support_idx": 0},
                               {"id": 2, "question": "q2", "answer": "Beta Province", "paragraph_support_idx": 1}],
    "paragraphs": [{"idx": 0, "title": "Gamma Person", "paragraph_text": P["Gamma Person"][0], "is_supporting": True},
                   {"idx": 1, "title": "Alpha City", "paragraph_text": P["Alpha City"][0], "is_supporting": True},
                   {"idx": 2, "title": "Theta River", "paragraph_text": P["Theta River"][0], "is_supporting": False}],
}


def openie_docs():
    return [{"idx": compute_mdhash_id(c, "chunk-"), "passage": c, "extracted_entities": sorted({x for t in tr for x in (t[0], t[2])}),
             "extracted_triples": tr} for c, tr in CORPUS.items()]


class FakeEmbedding:
    """Hashed bag-of-words, L2-normalized: deterministic and similarity-bearing."""
    dim = 64

    def __init__(self):
        self.calls = 0

    def batch_encode(self, texts, **kwargs):
        if isinstance(texts, str):
            texts = [texts]
        self.calls += 1
        out = []
        for t in texts:
            v = np.full(self.dim, 0.01, dtype=np.float32)
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            out.append(v / np.linalg.norm(v))
        return np.asarray(out)


class FakeLLM:
    """Filter: keeps every candidate fact. Records every prompt."""

    def __init__(self):
        self.prompts = []

    def infer(self, messages, **kwargs):
        self.prompts.append(json.dumps(messages))
        last = messages[-1]["content"]
        if "fact_before_filter" in last:
            facts = json.loads(last.split("[[ ## fact_before_filter ## ]]\n")[1].split("\n\nRespond")[0])
            return f'[[ ## fact_after_filter ## ]]\n{json.dumps(facts)}\n\n[[ ## completed ## ]]', {}, False
        return "Answer: mocked", {}, False


class FakeOpenIE:
    def __init__(self):
        self.calls = 0

    def batch_openie(self, rows):
        self.calls += 1
        ner, tri = {}, {}
        for cid, row in rows.items():
            triples = CORPUS[row["content"]]
            ner[cid] = NerRawOutput(cid, "", sorted({x for t in triples for x in (t[0], t[2])}), {})
            tri[cid] = TripleRawOutput(cid, "", triples, {})
        return ner, tri


def config(save_dir):
    return BaseConfig(save_dir=str(save_dir), embedding_model_name="fake", llm_name="fake", linking_top_k=5,
                      retrieval_top_k=200, qa_top_k=5)


def make(cls, save_dir, emb=None, llm=None):
    rag = cls(global_config=config(save_dir), extraction_llm=llm or FakeLLM(), qa_llm=None,
              embedding_model=emb or FakeEmbedding(), index_identity="fake-components-v1")
    return rag


@pytest.fixture(scope="module")
def base_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("base") / "base_save"
    rag = make(HippoRAG, d)
    rag.openie = FakeOpenIE()
    rag.index(DOCS)
    rag.close()
    return d


@pytest.fixture(scope="module")
def target():
    targets, stats = select_targets.select_targets([SAMPLE], openie_docs(), n_candidates=10)
    assert len(targets) == 1, stats
    return targets[0]


WD = "fake_fake"


def build_cell(base_dir, tmp_path, target, n, k, llm=None, shared_cache=None, cls=AttributionHippoRAG):
    variants = inject.cell_variants([target], n, k)
    cell_dir = tmp_path / f"cell_n{n}_k{k}"
    prepare_cell(base_dir, cell_dir, WD, variants, shared_cache)
    base_ids = {ns: vectors.store_ids(base_dir / WD, ns) for ns in ("chunk", "fact", "entity")}
    table = vectors.embed_plan(vectors.plan_texts([target], base_ids), FakeEmbedding())
    real_emb = FakeEmbedding()
    rag = make(cls, cell_dir, emb=real_emb, llm=llm)
    frozen = vectors.FrozenEmbedder(table)
    rag.install_frozen_embedder(frozen)
    stats = index_cell(rag, variants, frozen)
    stats["real_embed_calls"] = real_emb.calls
    rag.preload_query_vectors(table, [target["question"]])
    return rag, variants, stats, table


# ---------------------------------------------------------------- step 1 -------------------------
def test_target_selection_and_swap(target):
    assert (target["s"], target["r"], target["o"]) == ("Alpha City", "is located in", "Beta Province")
    assert target["o_prime"] in {"Zeta Province", "Omega Province", "Sigma Province"}
    assert target["o"] not in target["swapped_body"] and target["o_prime"] in target["swapped_body"]
    assert [target["s"], target["r"], target["o_prime"]] in target["swapped_triples"]
    assert target["freq_oprime_graph"] == 1 and target["stratum"] == "rare"
    assert target["freq_o_graph"] == 2          # Alpha City passage + Theta River passage


def test_collision_drops_second_target():
    twin = json.loads(json.dumps(SAMPLE))
    twin["id"] = "2hop__twin"
    targets, stats = select_targets.select_targets([SAMPLE, twin], openie_docs(), n_candidates=10)
    assert len(targets) == 1 and stats["rejections"]["entity/passage collision with an earlier target"] == 1


def test_o_prime_excludes_question_paragraphs():
    s = json.loads(json.dumps(SAMPLE))
    s["paragraphs"].append({"idx": 3, "title": "Delta Town", "paragraph_text": P["Delta Town"][0], "is_supporting": False})
    targets, _ = select_targets.select_targets([s], openie_docs(), n_candidates=10)
    assert targets[0]["o_prime"] != "Zeta Province"


# ---------------------------------------------------------------- step 2 -------------------------
def test_variant_text_independent_of_cell(target):
    a = {v["content"] for v in inject.cell_variants([target], 1, 2)}
    b = {v["content"] for v in inject.cell_variants([target], 3, 5)}
    assert a <= b
    ids = [v["chunk_id"] for v in inject.cell_variants([target], 3, 5)]
    assert len(ids) == len(set(ids)) == 2 + 5


def test_exact_copy_dedups_to_one_chunk(base_dir, tmp_path, target):
    rag, _, _, _ = build_cell(base_dir, tmp_path, target, 1, 0)
    before = len(rag.chunk_embedding_store.get_all_ids())
    rag.openie = FakeOpenIE()
    rag.index([target["gold_chunk"]])
    assert len(rag.chunk_embedding_store.get_all_ids()) == before


def test_variants_nodes_facts_edges(base_dir, tmp_path, target):
    n, k = 3, 2
    base = make(HippoRAG, base_dir)
    base_chunks, base_facts = len(base.chunk_embedding_store.get_all_ids()), len(base.fact_embedding_store.get_all_ids())
    base_vertices = base.graph.vcount()
    base.close()
    rag, variants, stats, _ = build_cell(base_dir, tmp_path, target, n, k)
    # distinct passage nodes
    assert len(rag.chunk_embedding_store.get_all_ids()) == base_chunks + (n - 1) + k
    assert rag.graph.vcount() == base_vertices + (n - 1) + k          # no new entity nodes
    # identical triples collapse: only (alpha city, is located in, o') is a new fact row
    assert len(rag.fact_embedding_store.get_all_ids()) == base_facts + 1
    # relation edge weight: +1 per passage carrying the triple
    names = rag.graph.vs["name"]

    def weight(a, b):
        ka, kb = compute_mdhash_id(tp(a), "entity-"), compute_mdhash_id(tp(b), "entity-")
        es = [e for e in rag.graph.es if {names[e.source], names[e.target]} == {ka, kb}]
        return es[0]["weight"] if es else 0.0
    assert weight(target["s"], target["o"]) == n
    assert weight(target["s"], target["o_prime"]) == k
    assert weight("Gamma Person", "Alpha City") == n + k                # unchanged triple, carried by every variant
    # 0 OpenIE calls (sentinel would have raised) and 0 real embedding calls
    assert stats["real_embed_calls"] == 0 and stats["vectors_served"] == (n - 1) + k + 1
    info, to_process = rag.load_existing_openie(rag.chunk_embedding_store.get_all_ids())
    assert len(to_process) == 0
    # insertion order recorded in the cell metadata
    seqs = [rag.chunk_metadata[v["chunk_id"]]["insert_seq"] for v in variants]
    assert seqs == sorted(seqs) and variants[-1]["role"] == "new"


def test_frozen_embedder_refuses_unknown_text():
    fe = vectors.FrozenEmbedder(vectors.VectorTable())
    with pytest.raises(KeyError):
        fe.batch_encode(["never embedded"])


def test_vector_table_roundtrip(tmp_path):
    t = vectors.VectorTable()
    t.add("chunk", ["a", "b"], np.eye(2))
    t.save(tmp_path / "v.npz")
    u = vectors.VectorTable.load(tmp_path / "v.npz")
    assert np.array_equal(u["b"], [0, 1]) and u.kinds["a"] == "chunk"
    with pytest.raises(ValueError):
        u.add("chunk", ["a"], np.eye(2)[:1])


# ---------------------------------------------------------------- step 4 -------------------------
def test_trace_matches_upstream_retrieve(base_dir, tmp_path, target):
    rag, _, _, _ = build_cell(base_dir, tmp_path, target, 3, 2)
    q = target["question"]
    ids, scores, trace = rag.trace_query(q)
    upstream = HippoRAG.retrieve(rag, [q], num_to_retrieve=len(ids))[0]
    mine = [rag.chunk_embedding_store.get_row(rag.passage_node_keys[i])["content"] for i in ids]
    assert mine == upstream.docs
    assert np.allclose(scores, upstream.doc_scores)


def test_attribution_record(base_dir, tmp_path, target):
    n, k = 3, 2
    rag, variants, _, _ = build_cell(base_dir, tmp_path, target, n, k)
    old = [compute_mdhash_id(target["gold_chunk"], "chunk-")] + [v["chunk_id"] for v in variants if v["role"] == "old"]
    new = [v["chunk_id"] for v in variants if v["role"] == "new"]
    rec = rag.attribute(target, old, new, injected_ids={v["chunk_id"] for v in variants})
    assert len(rec["stage_a"]) == 5 and all("score" in f for f in rec["stage_a"])
    assert rec["stage_b"]["kept"] == [f["fact"] for f in rec["stage_a"]]       # fake filter keeps all
    assert rec["fallback_dense"] is False
    seeds = rec["stage_c"]["seeds"]
    assert set(seeds) >= {"s", "o", "o_prime", *old, *new}
    assert all(seeds[c] > 0 for c in old + new)                               # every passage gets a dense seed
    for arm in ("hipporag", "dense"):
        r = rec[arm]
        assert set(r["passages"]) == set(old + new)
        assert r["margin_old_minus_new"] == pytest.approx(r["best_old"] - r["best_new"])
        assert "outranks_old" not in r                                         # tolerance applied at analysis time
        assert r["contamination_at5"] == sum(1 for t in r["top5"] if t["role"] == "old")
        assert r["correction_at5"] == any(t["role"] == "new" for t in r["top5"])
    # PPR score symmetry: identical-triple old copies get identical PPR scores up to their dense seed
    ppr_new = [rec["hipporag"]["passages"][c]["score"] for c in new]
    assert len(ppr_new) == k


def test_k0_has_no_outranks(base_dir, tmp_path, target):
    rag, variants, _, _ = build_cell(base_dir, tmp_path, target, 1, 0)
    rec = rag.attribute(target, [compute_mdhash_id(target["gold_chunk"], "chunk-")], [])
    assert rec["hipporag"]["best_new"] is None and rec["hipporag"]["correction_at5"] is None


def test_outranks_tolerance():
    assert outranks_old(1.0, 0.5) == "outranks"
    assert outranks_old(0.5, 1.0) == "loses"
    assert outranks_old(1.0, 0.995, tolerance=0.01) == "near_tie"
    assert outranks_old(1.0, 0.98, tolerance=0.01) == "outranks"
    assert outranks_old(None, 1.0) is None


# ---------------------------------------------------------------- step 5 -------------------------
def test_fix_drops_older_conflicting_fact(base_dir, tmp_path, target):
    rag, variants, _, _ = build_cell(base_dir, tmp_path, target, 1, 2)
    old_fact = [tp(target["s"]), tp(target["r"]), tp(target["o"])]
    new_fact = [tp(target["s"]), tp(target["r"]), tp(target["o_prime"])]
    rec0 = rag.attribute(target, [compute_mdhash_id(target["gold_chunk"], "chunk-")], [v["chunk_id"] for v in variants])
    assert rec0["flags"]["old_fact_kept"] and rec0["flags"]["new_fact_kept"]
    rag.apply_fix = True
    rec1 = rag.attribute(target, [compute_mdhash_id(target["gold_chunk"], "chunk-")], [v["chunk_id"] for v in variants])
    assert rec1["fix_trace"]["dropped"] == [{"fact": old_fact, "recency": 0}]
    assert new_fact in rec1["fix_trace"]["kept"] and old_fact not in rec1["fix_trace"]["kept"]
    # unchanged facts are untouched
    assert len(rec1["fix_trace"]["kept"]) == len(rec0["stage_b"]["kept"]) - 1


def test_fix_noop_without_conflict(base_dir, tmp_path, target):
    rag, _, _, _ = build_cell(base_dir, tmp_path, target, 3, 0)
    rag.apply_fix = True
    rec = rag.attribute(target, [compute_mdhash_id(target["gold_chunk"], "chunk-")], [])
    assert rec["fix_trace"]["dropped"] == []


def test_canonicalization_hook_is_used(base_dir, tmp_path, target, monkeypatch):
    from experiments.extension import attrib_rag
    rag, variants, _, _ = build_cell(base_dir, tmp_path, target, 1, 1)
    rag.apply_fix = True
    import itertools
    counter = itertools.count()
    monkeypatch.setattr(attrib_rag, "canonical_fact_key", lambda s, r: (s, r, next(counter)))   # no two facts share a key
    rec = rag.attribute(target, [compute_mdhash_id(target["gold_chunk"], "chunk-")], [v["chunk_id"] for v in variants])
    assert rec["fix_trace"]["dropped"] == []


# ---------------------------------------------------------------- cache reuse --------------------
def test_filter_prompt_repeats_across_k_ge_1_cells(base_dir, tmp_path, target):
    prompts = {}
    for n, k in ((1, 1), (1, 3), (3, 2), (3, 5)):
        llm = FakeLLM()
        rag, _, _, _ = build_cell(base_dir, tmp_path, target, n, k, llm=llm)
        rag.trace_query(target["question"])
        prompts[(n, k)] = llm.prompts[-1]
    assert len(set(prompts.values())) == 1
    llm0 = FakeLLM()
    rag, _, _, _ = build_cell(base_dir, tmp_path, target, 3, 0, llm=llm0)
    rag.trace_query(target["question"])
    assert llm0.prompts[-1] != prompts[(1, 1)]


def test_shared_cache_symlink(base_dir, tmp_path, target):
    shared = tmp_path / "shared_cache"
    build_cell(base_dir, tmp_path, target, 1, 1, shared_cache=shared)
    link = tmp_path / "cell_n1_k1" / "llm_cache"
    assert link.is_symlink() and link.resolve() == shared.resolve()


def test_base_untouched(base_dir, tmp_path, target):
    def snapshot():
        return {p.relative_to(base_dir): hashlib.md5(p.read_bytes()).hexdigest()
                for p in base_dir.rglob("*") if p.is_file() and not p.name.endswith(".lock")}
    before = snapshot()
    build_cell(base_dir, tmp_path, target, 3, 5)
    assert snapshot() == before


# ---------------------------------------------------------------- step 6 -------------------------
def test_long_context_prompt_and_scorer(target):
    msgs = long_context.build_messages(SAMPLE, target, 3, 2)
    user = msgs[-1]["content"]
    for p in SAMPLE["paragraphs"]:
        assert chunk_text(p["title"], p["paragraph_text"]) in user
    for v in inject.cell_variants([target], 3, 2):
        assert v["content"] in user
    assert user.count("Wikipedia Title: ") == len(SAMPLE["paragraphs"]) + 2 + 2
    assert user.endswith("Question: " + SAMPLE["question"] + "\nThought: ")
    o, op = target["o"], target["o_prime"]
    assert long_context.classify(long_context.parse_answer(f"... Answer: {op}."), o, op) == "o_prime"
    assert long_context.classify(f"The {o}", o, op) == "o"
    assert long_context.classify("unknown", o, op) == "neither"
    assert long_context.classify(f"{o} or {op}", o, op) == "both"


# ---------------------------------------------------------------- config -------------------------
def test_capture_config_matches_launch(tmp_path):
    from experiments.extension.common import capture_config
    c = capture_config(str(tmp_path / "cell"))
    assert c.save_dir == str(tmp_path / "cell") + "_musique"
    assert (c.llm_name, c.embedding_model_name, c.embedding_batch_size, c.linking_top_k) == ("gpt-4o-mini", "text-embedding-3-small", 128, 5)
    assert c.embedding_base_url == c.llm_base_url == "https://api.aicredits.in/v1"


# ---------------------------------------------------------------- step 7 -------------------------
def test_filter_plan_counts():
    from experiments.extension.run_cells import CELLS, filter_plan
    plan = filter_plan(100)
    assert len(CELLS) == 10
    assert sum(new for new, _ in plan.values()) == 200            # one k=0 and one k>=1 prompt per question
    assert plan[(1, 0)] == (100, 100) and plan[(1, 1)] == (100, 100) and plan[(3, 5)] == (0, 200)


# ---------------------------------------------------------------- targets v2 ---------------------
def _unit(*xs):
    v = np.asarray(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


# cosine to "beta province": sigma 0.995 (near-duplicate, excluded), omega 0.8, zeta 0.5
V2_VECTORS = {"beta province": _unit(1, 0, 0), "sigma province": _unit(1, 0.1, 0),
              "omega province": _unit(0.8, 0.6, 0), "zeta province": _unit(0.5, 0, 0.866)}


def _candidates(messages):
    return messages[-1]["content"].split("Candidates:\n")[1].split("\n\n")[0].splitlines()


def _picker(name, single="yes", log=None):
    def infer(messages):
        if log is not None:
            log.append(messages)
        num = next((l.split(".")[0] for l in _candidates(messages) if name and name in l), "none")
        return f"PICK: {num}\nSINGLE: {single}", {"prompt_tokens": 100, "completion_tokens": 6}, False
    return infer


def test_v2_ranking_excludes_near_duplicates():
    from experiments.extension.select_targets_v2 import ranked
    pool = [("Sigma Province", 1), ("Omega Province", 1), ("Zeta Province", 1), ("No Vector", 1)]
    out = ranked("Beta Province", pool, V2_VECTORS)
    assert [c for c, _, _ in out] == ["Omega Province", "Zeta Province"]
    assert out[0][2] == pytest.approx(0.8, abs=1e-4)


def test_v2_parse_response():
    from experiments.extension.select_targets_v2 import parse_response
    assert parse_response("PICK: 3\nSINGLE: yes", 8) == (2, True)
    assert parse_response("pick: none\nsingle: no", 8) == (None, False)
    assert parse_response("PICK: 9\nSINGLE: yes", 8) == (None, True)
    assert parse_response("I think 3", 8) == (None, None)


def test_v2_selection_with_mock_picker():
    from experiments.extension.select_targets_v2 import select_v2
    seen = []
    targets, stats, picks = select_v2([SAMPLE], openie_docs(), _picker("Omega Province", log=seen), V2_VECTORS)
    assert len(seen) == 1
    prompt = seen[0][-1]["content"]
    assert "Beta Province" in prompt and "Sigma Province" not in prompt and "SINGLE" in prompt
    t = targets[0]
    assert t["o_prime"] == "Omega Province" and t["o_prime_source"] == "gpt-4o-mini" and not t["stratum_changed"]
    assert [t["s"], t["r"], "Omega Province"] in t["swapped_triples"]
    assert stats["usage"] == {"calls": 1, "cache_hits": 0, "prompt_tokens": 100, "completion_tokens": 6}


def test_v2_drops_multi_valued():
    from experiments.extension.select_targets_v2 import select_v2
    targets, stats, _ = select_v2([SAMPLE], openie_docs(), _picker("Omega Province", single="no"), V2_VECTORS)
    assert targets == [] and stats["rejections"]["LLM: multi-valued or unparseable SINGLE"] == 1
    docs = openie_docs() + [{"idx": "chunk-x", "passage": "Extra\nAlpha City is located in Kappa Region.",
                             "extracted_entities": [], "extracted_triples": [["Alpha City", "is located in", "Kappa Region"]]}]
    calls = []
    targets, stats, _ = select_v2([SAMPLE], docs, _picker("Omega Province", log=calls), V2_VECTORS)
    assert targets == [] and calls == []                                   # dropped offline, no LLM call
    assert stats["rejections"]["multi-valued in corpus (subject has >= 2 objects for the relation)"] == 1


def test_v2_none_retries_other_stratum(monkeypatch):
    from experiments.extension import select_targets
    from experiments.extension.select_targets_v2 import select_v2
    monkeypatch.setattr(select_targets, "COMMON_MIN", 1)       # synthetic corpus: every o' is in both pools
    seen = []
    targets, stats, picks = select_v2([SAMPLE], openie_docs(), _picker(None, log=seen), V2_VECTORS)
    assert len(seen) == 2 and targets == []                    # none, retry once, none again
    assert [c["stratum"] for c in picks[0]["calls"]] == ["common", "rare"] or \
        [c["stratum"] for c in picks[0]["calls"]] == ["rare", "common"]
    answers = iter(["PICK: none\nSINGLE: yes", None])

    def none_then_omega(messages):
        text = next(answers)
        if text is None:
            num = next(l.split(".")[0] for l in _candidates(messages) if "Omega Province" in l)
            text = f"PICK: {num}\nSINGLE: yes"
        return text, {}, False
    targets, stats, _ = select_v2([SAMPLE], openie_docs(), none_then_omega, V2_VECTORS)
    assert targets[0]["stratum_changed"] and targets[0]["stratum"] != targets[0]["assigned_stratum"]
    assert stats["stratum_changes"] == 1


# ---------------------------------------------------------------- analysis -----------------------
def _rec(cand=True, kept=True, seeded=True, best_new=1.0, best_old=0.5, in_top5=False, k=1, fix=False):
    nf = [tp("Alpha City"), tp("is located in"), tp("Zeta Province")]
    kept_list = [nf] if kept else []
    return {"target_id": "t", "cell": [1, k], "fix": fix, "flags": {"new_fact_in_candidates": cand},
            "stage_b": {"kept": kept_list}, "fix_trace": {"kept": kept_list, "dropped": []},
            "stage_c": {"seeds": {"o_prime": 0.1 if seeded else 0.0}},
            "hipporag": {"correction_at5": (in_top5 if k else None), "best_new": best_new if k else None, "best_old": best_old}}


def test_first_failure_stages():
    from experiments.extension.analysis import STAGE_ORDER, first_failure
    t = {"s": "Alpha City", "r": "is located in", "o_prime": "Zeta Province"}
    assert first_failure(_rec(cand=False, kept=False, seeded=False), "hipporag", t, 0.01) == "A"
    assert first_failure(_rec(kept=False, seeded=False), "hipporag", t, 0.01) == "B"
    assert first_failure(_rec(seeded=False), "hipporag", t, 0.01) == "C"
    assert first_failure(_rec(best_new=0.5, best_old=1.0), "hipporag", t, 0.01) == "D"
    assert first_failure(_rec(best_new=0.995, best_old=1.0), "hipporag", t, 0.01) == "E_tie"     # near tie
    assert first_failure(_rec(best_new=0.995, best_old=1.0), "hipporag", t, 0.0) == "D"      # tolerance matters
    assert first_failure(_rec(), "hipporag", t, 0.01) == "E_crowd"
    assert first_failure(_rec(in_top5=True, cand=False), "hipporag", t, 0.01) == "ok"
    assert first_failure(_rec(k=0), "hipporag", t, 0.01) is None
    # configurable order
    assert first_failure(_rec(cand=False, seeded=False), "hipporag", t, 0.01, order=("C", "A", "B", "D", "E_tie", "E_crowd")) == "C"
    assert STAGE_ORDER == ("A", "B", "C", "D", "E_tie", "E_crowd")


def test_analysis_end_to_end(base_dir, tmp_path, target):
    from experiments.extension import analysis
    results = tmp_path / "results"
    results.mkdir()
    for n, k in ((1, 0), (1, 1), (3, 2)):
        rag, variants, _, _ = build_cell(base_dir, tmp_path, target, n, k)
        old = [compute_mdhash_id(target["gold_chunk"], "chunk-")] + [v["chunk_id"] for v in variants if v["role"] == "old"]
        new = [v["chunk_id"] for v in variants if v["role"] == "new"]
        with open(results / f"cell_n{n}_k{k}.jsonl", "w") as f:
            for fix in (False, True):
                rag.apply_fix = fix
                rec = rag.attribute(target, old, new, injected_ids={v["chunk_id"] for v in variants})
                rec.update(cell=[n, k])
                f.write(json.dumps(rec, default=float) + "\n")
    targets_path = tmp_path / "targets.jsonl"
    targets_path.write_text(json.dumps(target) + "\n")
    out = tmp_path / "analysis"
    sys.argv = ["analysis.py", "--results", str(results), "--targets", str(targets_path), "--out", str(out)]
    analysis.main()
    for name in ("metrics.csv", "attribution.csv", "summary.md", "correction_at5.png", "contamination_at5.png",
                 "outranks_old.png", "attribution.png"):
        assert (out / name).stat().st_size > 0
    rows = analysis.flatten(analysis.load_records(results), {target["target_id"]: target})
    assert {r["arm"] for r in rows} == {"dense", "hipporag", "hipporag_fix"}
    assert len(rows) == 3 * 3                                       # 3 cells x 3 arms
    table = analysis.summarize(rows)
    k0 = [e for e in table if e["k"] == 0]
    assert all(e["correction_at5"] is None and e["outranks@0.01"] is None for e in k0)


# ---------------------------------------------------------------- targets v3 ---------------------
def test_doubled_token_check():
    from experiments.extension.select_targets_v3 import doubled_token_hits
    body = "She was the mother of emperor Ahmad Shah Bahadur."
    assert doubled_token_hits(body, "Ahmad Shah Bahadur", "Emperor Wencheng") == ["...emperor Emperor Wencheng"]
    assert doubled_token_hits("It is in Richland County, South Carolina.", "Richland County", "Vernon County") == []
    assert doubled_token_hits("Born in Paris city centre.", "Paris", "Mexico City") == ["Mexico City city..."]


def _gt(tid, s, o, op, gold):
    return {"target_id": tid, "s": s, "o": o, "o_prime": op, "gold_chunk": gold}


def test_group_colouring_is_collision_free():
    from experiments.extension.select_targets_v3 import assign_groups, check_groups
    ts = [_gt("a", "S1", "O1", "X", "p1"), _gt("b", "S2", "O2", "X", "p2"),       # share o' X
          _gt("c", "S3", "O1", "Y", "p3"),                                         # shares o O1 with a
          _gt("d", "S4", "O4", "Z", "p1"),                                         # shares gold passage with a
          _gt("e", "S5", "O5", "W", "p5")]                                         # free
    n = assign_groups(ts)
    check_groups(ts)
    g = {t["target_id"]: t["group"] for t in ts}
    assert g["a"] != g["b"] and g["a"] != g["c"] and g["a"] != g["d"]
    assert n == 2 and g["e"] == 0
    ts[1]["group"] = ts[0]["group"]
    with pytest.raises(AssertionError):
        check_groups(ts)


def test_groups_get_separate_cells(base_dir, tmp_path, target):
    """Two groups in one cell: separate clones; each index carries only its own group's variants."""
    from experiments.extension.run_cells import cell_prefix, groups_of
    t2 = json.loads(json.dumps(target))
    t2.update(target_id="other", group=1)
    t1 = dict(target, group=0)
    groups = groups_of([t1, t2])
    assert sorted(groups) == [0, 1] and [t["target_id"] for t in groups[1]] == ["other"]
    assert cell_prefix(tmp_path, 3, 5, 0) != cell_prefix(tmp_path, 3, 5, 1)
    assert groups_of([target]) == {0: [target]}                                  # v1/v2 targets: one group


# ---------------------------------------------------------------- targets v4 ---------------------
def test_v4_candidate_checks():
    from experiments.extension.select_targets_v4 import check_candidate, parse_candidates
    para = SAMPLE["paragraphs"][1]
    triple = ("Alpha City", "is located in", "Beta Province")
    ok = lambda c: check_candidate(c, SAMPLE, para, triple)
    assert ok("Gamma Region") is None
    assert ok("beta province") == "equals o"
    assert ok("Beta Province North") == "substring of/contains o"
    assert ok("Theta River") == "in the question's own paragraphs"
    assert ok("1901") == "surface shape differs"
    assert ok("the Province") == "surface shape differs"
    assert ok("") == "empty"
    assert parse_candidates('Sure: {"candidates": ["A B", " ", "C"]}') == ["A B", "C"]
    assert parse_candidates("no json") == []


def test_frequency_split_needs_15_per_bin():
    from experiments.extension.analysis import slice_map
    ts = {f"t{i}": {"freq_oprime_graph": f, "freq_o_graph": 1} for i, f in enumerate([0] * 15 + [3] * 15 + [20] * 15)}
    labels, report = slice_map(ts)
    assert report["o_prime_freq"]["used"] and "o_prime_freq:absent" in labels["t0"]
    assert not report["o_freq"]["used"] and all("o_freq" not in " ".join(v) for v in labels.values())
    ts["t44"]["freq_oprime_graph"] = 3                                   # >=10 bin drops to 14
    labels, report = slice_map(ts)
    assert not report["o_prime_freq"]["used"] and labels["t0"] == ["all"]


def test_v5_checks_probe_and_knows_split():
    from experiments.extension.analysis import slice_map
    from experiments.extension.select_targets_v5 import knows, parse_checks
    assert parse_checks("TYPE: yes\nCOHERENT: Yes\nPOSSIBLE: no") == {"type": True, "coherent": True, "possible": False}
    assert parse_checks("TYPE: yes") == {"type": True, "coherent": None, "possible": None}
    assert knows("Richland County", "Richland County") == (True, True)
    assert knows("Richland County, South Carolina", "Richland County") == (False, True)
    assert knows("The 1st of June", "June 1982") == (False, False)
    assert knows("June 1982.", "8 June 1982", aliases=["June 1982"]) == (True, True)
    ts = {f"t{i}": {"model_knows_o": i % 2 == 0, "freq_oprime_graph": 0, "freq_o_graph": 1} for i in range(30)}
    labels, report = slice_map(ts)
    assert report["model_knows_o"] == {"yes": 15, "no": 15, "used": True}
    assert "model_knows_o:yes" in labels["t0"] and "model_knows_o:no" in labels["t1"]
    ts.pop("t0")
    _, report = slice_map(ts)
    assert not report["model_knows_o"]["used"]


def test_review_keep_marks_to_final(target):
    from experiments.extension.finalize_targets import finalize, read_marks, report
    from experiments.extension.select_targets_v5 import review_markdown
    ts = []
    for i, f in enumerate((0, 3)):
        t = dict(target, target_id=f"t{i}", group=0, freq_oprime_graph=f, model_knows_o=bool(i),
                 checks={"type": True, "coherent": True, "possible": True}, probe_answer_titled="x | y",
                 probe_answer_bare="z", gold_chunk=f"p{i}", s=f"S{i}", o=target["o"], o_prime=target["o_prime"])
        ts.append(t)
    ts[1]["o"] = ts[0]["o"]                        # same o in one group would collide; give t1 its own group
    ts[1]["group"] = 1
    text = review_markdown(ts, [])
    marks = read_marks(text)
    assert marks == {"t0": "y", "t1": "y"}                                 # default y, pipe in a cell escaped
    final = finalize(ts, {**marks, "t1": "n"})
    assert [t["target_id"] for t in final] == ["t0"]
    r = report(final)
    assert r["final"] == 1 and r["model_knows_o"] == {"no": 1}
    with pytest.raises(ValueError):
        finalize(ts, {"t0": "y"})                                          # missing mark
    with pytest.raises(ValueError):
        read_marks(text.replace("| y | 1 |", "| maybe | 1 |"))             # invalid mark


def test_v4_one_question_per_passage():
    from experiments.extension.select_targets_v4 import anchors_one_per_passage
    twin = json.loads(json.dumps(SAMPLE))
    twin["id"] = "2hop__twin"
    chosen, reasons = anchors_one_per_passage([SAMPLE, twin], openie_docs())
    assert len(chosen) == 1 and reasons["another question on the same gold passage (one kept per passage)"] == 1


def test_novel_o_prime_becomes_new_entity_node(base_dir, tmp_path, target):
    """A generated o' absent from the corpus: one new entity node, vector served from the frozen table, seeded."""
    t = json.loads(json.dumps(target))
    para = {"title": t["title"], "paragraph_text": t["body"], "idx": t["para_idx"]}
    t["o_prime"] = "Novel Province"
    t["swapped_body"], t["swapped_triples"] = select_targets.swap_passage(para, t["triples"], t["o"], t["o_prime"])
    t["swapped_entities"] = [t["o_prime"] if e == t["o"] else e for e in t["entities"]]
    base = make(HippoRAG, base_dir)
    base_vertices = base.graph.vcount()
    base.close()
    rag, variants, stats, table = build_cell(base_dir, tmp_path, t, 1, 2)
    assert "novel province" in table and table.kinds["novel province"] == "entity"
    assert rag.graph.vcount() == base_vertices + 2 + 1                       # 2 corrections + 1 new entity
    assert stats["real_embed_calls"] == 0
    old = [compute_mdhash_id(t["gold_chunk"], "chunk-")]
    rec = rag.attribute(t, old, [v["chunk_id"] for v in variants])
    assert rec["stage_c"]["seeds"]["o_prime"] is not None                     # node exists in the graph
