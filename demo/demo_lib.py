"""Shared code for the Presentation 2 reproduction demo (`demo/run_demo.py`). src/ is not edited.

Traces one MuSiQue question through HippoRAG 2 on the n=500 index, stage by stage, with upstream methods:
  1 query -> triple  HippoRAG.get_fact_scores; the top linking_top_k candidates are recorded by
                     AttributionHippoRAG.rerank_facts (experiments/extension/attrib_rag.py), which then calls upstream
  2 filter           upstream rerank_facts -> rerank_filter (one gpt-4o-mini call, LLM cache)
  3 seeds            the reset vector graph_search_with_fact_entities hands to run_ppr (recorded by the run_ppr override)
  4 PPR              upstream run_ppr; the all-node top 10 is recomputed with the identical igraph call and checked
                     against upstream's passage scores
  5 top 5            the passage ranking run_ppr returns; dense top 5 from dense_passage_retrieval (same query vector)
  6 reader           upstream HippoRAG.qa on the top qa_top_k passages (one gpt-4o-mini call, LLM cache)

The index is an APFS clone of outputs/hipporag_n500_musique (incl. its LLM cache) under demo/index/, so nothing
under outputs/ is written.
"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SOURCE_SAVE_DIR = REPO_ROOT / "outputs" / "hipporag_n500_musique"
INDEX_PREFIX = DEMO_DIR / "index" / "hipporag_n500"          # run_subset's config appends "_musique"
INDEX_SAVE_DIR = Path(str(INDEX_PREFIX) + "_musique")
WORKING_DIR_NAME = "gpt-4o-mini_text-embedding-3-small"
TRACES_DIR = DEMO_DIR / "traces"
RECORDED = {"hipporag": REPO_ROOT / "results" / "musique_n500" / "hipporag_per_query_n500.json",
            "dense": REPO_ROOT / "results" / "musique_n500" / "dense_per_query_n500.json"}
DATASET_PATH = REPO_ROOT / "reproduce" / "dataset" / "musique.json"
DEMO_QUESTIONS = (193, 96)   # the 2 chosen from the 9 where HippoRAG has a gold passage in its top 5 and dense has none


# ---- index clone ---------------------------------------------------------------------------------------
def make_index():
    """cp -c (APFS clonefile) of the n=500 save dir, LLM cache included; the source is only read."""
    if INDEX_SAVE_DIR.exists():
        raise SystemExit(f"{INDEX_SAVE_DIR} exists; delete it first to re-clone")
    INDEX_SAVE_DIR.mkdir(parents=True)
    for entry in sorted(SOURCE_SAVE_DIR.iterdir()):
        if entry.name.endswith(".lock") or entry.name.startswith("per_query"):
            continue
        subprocess.run(["cp", "-c", "-R", str(entry), str(INDEX_SAVE_DIR / entry.name)], check=True)
    for lock in INDEX_SAVE_DIR.rglob("*.lock"):
        lock.unlink()
    return INDEX_SAVE_DIR


# ---- data ----------------------------------------------------------------------------------------------
def load_sample(index):
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))[index]


def gold_doc_texts(sample):
    """Same construction as experiments/run_subset.get_gold_docs: 'title\\ntext' of supporting paragraphs."""
    return [f"{p['title']}\n{p['paragraph_text']}" for p in sample["paragraphs"] if p["is_supporting"]]


def recorded_row(arm, index):
    row = json.loads(RECORDED[arm].read_text(encoding="utf-8"))[index]
    assert row["index"] == index
    return row


def title_of(passage_text):
    return passage_text.split("\n", 1)[0]


def git_state():
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "--quiet", "upstream-base", "--", "src", "main.py"], cwd=REPO_ROOT).returncode
    return {"commit": head, "src_main_identical_to_upstream_base": diff == 0}


# ---- live: key, rag, meter -----------------------------------------------------------------------------
def load_key():
    """The gateway key from the environment, else from .env (never printed). OPENAI_BASE_URL stays unset."""
    os.environ.pop("OPENAI_BASE_URL", None)
    if os.environ.get("OPENAI_API_KEY"):
        return
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.startswith("OPENAI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("\"'")
            if value:
                os.environ["OPENAI_API_KEY"] = value
                return
    raise SystemExit("OPENAI_API_KEY is not set and .env has no value")


def build_rag():
    from experiments.extension.attrib_rag import AttributionHippoRAG
    from experiments.extension.common import capture_config
    if not INDEX_SAVE_DIR.exists():
        raise SystemExit(f"{INDEX_SAVE_DIR} missing; run: .venv/bin/python demo/run_demo.py --make_index")
    config = capture_config(str(INDEX_PREFIX))   # exactly run_subset.py's BaseConfig for the reproduction runs
    assert Path(config.save_dir).resolve() == INDEX_SAVE_DIR.resolve(), config.save_dir
    return AttributionHippoRAG(global_config=config)


class CallMeter:
    """Counts paid calls: the filter's LLM function, the reader's LLM and the embedding model (query vectors)."""

    def __init__(self, rag):
        import tiktoken
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.llm = []            # {"stage", "cache_hit", "prompt_tokens", "completion_tokens"}
        self.embed_texts = 0
        self.embed_tokens = 0
        self.embed_calls = 0
        self._wrap_llm(rag.rerank_filter, "llm_infer_fn", "filter")
        self._wrap_llm(rag.qa_llm, "infer", "reader")
        original = rag.embedding_model.batch_encode

        def batch_encode(texts, **kwargs):
            items = [texts] if isinstance(texts, str) else list(texts)
            self.embed_calls += 1
            self.embed_texts += len(items)
            self.embed_tokens += sum(len(self.enc.encode(t)) for t in items)
            return original(texts, **kwargs)
        rag.embedding_model.batch_encode = batch_encode

    def _wrap_llm(self, owner, attr, stage):
        original = getattr(owner, attr)

        def wrapped(*args, **kwargs):
            message, metadata, cache_hit = original(*args, **kwargs)
            self.llm.append({"stage": stage, "cache_hit": bool(cache_hit),
                             "prompt_tokens": int(metadata.get("prompt_tokens", 0) or 0),
                             "completion_tokens": int(metadata.get("completion_tokens", 0) or 0)})
            return message, metadata, cache_hit
        setattr(owner, attr, wrapped)

    def summary(self):
        from experiments.extension.common import PRICE_USD_PER_M, inr
        paid = [c for c in self.llm if not c["cache_hit"]]
        tin, tout = sum(c["prompt_tokens"] for c in paid), sum(c["completion_tokens"] for c in paid)
        usd = (tin * PRICE_USD_PER_M["gpt-4o-mini_in"] + tout * PRICE_USD_PER_M["gpt-4o-mini_out"]
               + self.embed_tokens * PRICE_USD_PER_M["text-embedding-3-small"]) / 1e6
        return {"llm_calls": [dict(c) for c in self.llm], "llm_paid_calls": len(paid),
                "llm_paid_tokens_in": tin, "llm_paid_tokens_out": tout,
                "embedding_calls": self.embed_calls, "embedding_texts": self.embed_texts,
                "embedding_tokens_tiktoken": self.embed_tokens,
                "inr_estimate": round(inr(usd), 4),
                "pricing": "list price x 1.1 at Rs 88/$ (experiments/extension/common.py:39-45)"}


# ---- the trace -----------------------------------------------------------------------------------------
def node_label(rag, v):
    vertex = rag.graph.vs[int(v)]
    name = vertex["name"]
    if name.startswith("chunk-"):
        return "passage", title_of(vertex["content"]), name
    return "entity", vertex["content"], name


def trace_question(rag, index, damping=None, passage_weight=None, run_reader=True):
    from src.hipporag.evaluation.qa_eval import QAExactMatch, QAF1Score
    from src.hipporag.utils.misc_utils import QuerySolution

    cfg = rag.global_config
    if damping is not None:
        cfg.damping = float(damping)
    if passage_weight is not None:
        cfg.passage_node_weight = float(passage_weight)
    sample = load_sample(index)
    question = sample["question"]
    gold_texts = set(gold_doc_texts(sample))

    ids, scores, tr = rag.trace_query(question)
    keys = [rag.passage_node_keys[i] for i in ids]
    content = lambda key: rag.chunk_embedding_store.get_row(key)["content"]

    out = {"index": index, "question": question, "gold_answers": [sample["answer"]] + sample.get("answer_aliases", []),
           "gold_titles": [title_of(t) for t in gold_doc_texts(sample)],
           "config": {"damping": cfg.damping, "passage_node_weight": cfg.passage_node_weight,
                      "linking_top_k": cfg.linking_top_k, "qa_top_k": cfg.qa_top_k, "retrieval_top_k": cfg.retrieval_top_k}}
    out["step1_query_to_triple"] = [{"rank": r + 1, "fact": f["fact"], "score": f["score"]} for r, f in enumerate(tr["stage_a"])]
    kept = tr["stage_b"]["kept"]
    out["step2_filter"] = {"input": [f["fact"] for f in tr["stage_a"]], "output": kept,
                           "removed": [f["fact"] for f in tr["stage_a"] if f["fact"] not in kept],
                           "error": tr["stage_b"]["error"], "fallback_to_dense": tr["fallback_dense"]}

    if not tr["fallback_dense"]:
        reset = tr["reset"]
        ent_idx = np.asarray(rag.entity_node_idxs)
        psg_idx = np.asarray(rag.passage_node_idxs)
        phrase = [(int(v), float(reset[v])) for v in ent_idx if reset[v] > 0]
        phrase.sort(key=lambda x: -x[1])
        psg = [(int(v), float(reset[v])) for v in psg_idx if reset[v] > 0]
        psg.sort(key=lambda x: -x[1])
        total = float(reset.sum())
        phrase_mass = float(sum(w for _, w in phrase))
        out["step3_seeds"] = {
            "phrase_seeds": [{"entity": rag.graph.vs[v]["content"], "reset_weight": w,
                              "share_of_reset": w / total,
                              "n_passages_with_entity": len(rag.ent_node_to_chunk_ids.get(rag.graph.vs[v]["name"], ()))}
                             for v, w in phrase],
            "passage_seeds_top10": [{"title": title_of(rag.graph.vs[v]["content"]), "reset_weight": w,
                                     "dense_score_minmax": w / cfg.passage_node_weight if cfg.passage_node_weight else None,
                                     "gold": rag.graph.vs[v]["content"] in gold_texts}
                                    for v, w in psg[:10]],
            "n_passage_seeds_nonzero": len(psg), "n_passages": int(len(psg_idx)),
            "reset_total": total, "phrase_mass": phrase_mass, "passage_mass": total - phrase_mass,
            "phrase_share": phrase_mass / total, "passage_share": (total - phrase_mass) / total,
            "rule": "phrase weight = mean over kept facts containing the entity of (fact score / #passages with the entity); "
                    "passage weight = min-max dense score x passage_node_weight (HippoRAG.py:2047-2102)"}
        # All-node PPR: the identical igraph call run_ppr makes (HippoRAG.py:2204-2212); its passage part must match.
        pr = np.asarray(rag.graph.personalized_pagerank(
            vertices=range(len(rag.node_name_to_vertex_idx)), damping=cfg.damping, directed=False,
            weights="weight", reset=reset, implementation="prpack"))
        upstream_ids, upstream_scores = tr["ppr"]
        check = pr[psg_idx][np.asarray(upstream_ids[:50])]
        if not np.allclose(check, np.asarray(upstream_scores[:50]), rtol=1e-9, atol=0):
            raise AssertionError("recomputed PPR does not match upstream run_ppr")
        top10 = np.argsort(pr)[::-1][:10]
        out["step4_ppr_top10"] = []
        for r, v in enumerate(top10):
            kind, label, name = node_label(rag, v)
            out["step4_ppr_top10"].append({"rank": r + 1, "type": kind, "label": label, "score": float(pr[v]),
                                           "reset_weight": float(reset[v]),
                                           "gold": kind == "passage" and rag.graph.vs[int(v)]["content"] in gold_texts})
        out["step4_check"] = "all-node PPR recomputed; passage scores equal upstream run_ppr (rtol 1e-9, top 50)"
    else:
        out["step3_seeds"] = None
        out["step4_ppr_top10"] = None

    top = cfg.qa_top_k
    out["step5_top5"] = [{"rank": r + 1, "chunk": k, "title": title_of(content(k)), "score": float(s),
                          "gold": content(k) in gold_texts} for r, (k, s) in enumerate(zip(keys[:top], scores[:top]))]
    d_ids, d_scores = rag.dense_passage_retrieval(question)
    dkeys = [rag.passage_node_keys[i] for i in d_ids[:top]]
    out["dense_top5"] = [{"rank": r + 1, "chunk": k, "title": title_of(content(k)), "score": float(s),
                          "gold": content(k) in gold_texts} for r, (k, s) in enumerate(zip(dkeys, d_scores[:top]))]
    out["recall_at_5"] = {"hipporag": sum(x["gold"] for x in out["step5_top5"]) / len(gold_texts),
                          "dense": sum(x["gold"] for x in out["dense_top5"]) / len(gold_texts)}

    if run_reader:
        sols, raw, _meta = rag.qa([QuerySolution(question=question, docs=[content(k) for k in keys[:top]],
                                                 doc_scores=np.asarray(scores[:top]))])
        answer = sols[0].answer
        f1 = QAF1Score(None).calculate_metric_scores([out["gold_answers"]], [answer])[0]["F1"]
        em = QAExactMatch(None).calculate_metric_scores([out["gold_answers"]], [answer])[0]["ExactMatch"]
        out["step6_reader"] = {"answer": answer, "raw_response": raw[0], "gold_answers": out["gold_answers"],
                               "F1": float(f1), "EM": float(em)}
    else:
        out["step6_reader"] = None

    rec_h, rec_d = recorded_row("hipporag", index), recorded_row("dense", index)
    live_titles = [x["title"] for x in out["step5_top5"]]
    out["recorded_n500_run"] = {
        "source": "results/musique_n500/hipporag_per_query_n500.json and dense_per_query_n500.json, row %d" % index,
        "hipporag_top5": [title_of(d) for d in rec_h["docs"][:top]], "hipporag_answer": rec_h["answer"],
        "dense_top5": [title_of(d) for d in rec_d["docs"][:top]], "dense_answer": rec_d["answer"],
        "live_top5_equals_recorded": live_titles == [title_of(d) for d in rec_h["docs"][:top]]}
    out["meta"] = {"generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                   "index": str(INDEX_SAVE_DIR.relative_to(REPO_ROOT)) + " (APFS clone of outputs/hipporag_n500_musique)",
                   "graph": {"nodes": rag.graph.vcount(), "edges": rag.graph.ecount()}, **git_state()}
    return out


# ---- rendering -----------------------------------------------------------------------------------------
class Style:
    def __init__(self, color):
        c = (lambda code: (lambda s: f"\033[{code}m{s}\033[0m")) if color else (lambda code: (lambda s: str(s)))
        self.bold, self.dim, self.green, self.red, self.cyan, self.yellow = c("1"), c("2"), c("32"), c("31"), c("36"), c("33")


def fact_str(f):
    return f"({f[0]} | {f[1]} | {f[2]})"


def render_terminal(t, color=True, pause=None):
    s = Style(color)
    say = print
    stop = pause or (lambda: None)
    gold = lambda g: s.green("GOLD") if g else "    "
    cfg = t["config"]
    say(s.bold(f"\nQ{t['index']}: {t['question']}"))
    say(s.dim(f"gold answer: {' / '.join(t['gold_answers'])}   gold passages: {' ; '.join(t['gold_titles'])}"))
    say(s.dim(f"damping {cfg['damping']}  passage_node_weight {cfg['passage_node_weight']}  linking_top_k {cfg['linking_top_k']}"))
    stop()
    say(s.cyan("\n[1] query -> triple  (cosine to every fact vector, min-max normalized; top 5)"))
    for x in t["step1_query_to_triple"]:
        say(f"  {x['rank']}. {x['score']:.3f}  {fact_str(x['fact'])}")
    stop()
    f = t["step2_filter"]
    say(s.cyan(f"\n[2] recognition-memory filter (gpt-4o-mini): {len(f['input'])} in -> {len(f['output'])} kept"))
    for x in f["input"]:
        say(f"  {s.green('keep') if x in f['output'] else s.red('drop')}  {fact_str(x)}")
    if f["fallback_to_dense"]:
        say(s.yellow("  no fact kept -> HippoRAG falls back to dense retrieval"))
    stop()
    if t["step3_seeds"]:
        sd = t["step3_seeds"]
        say(s.cyan(f"\n[3] PPR reset vector: phrases {sd['phrase_share']:.1%} of mass, passages {sd['passage_share']:.1%}"))
        for x in sd["phrase_seeds"]:
            say(f"  entity   {x['reset_weight']:.4f}  {x['entity']}  (in {x['n_passages_with_entity']} passage(s))")
        say(s.dim(f"  passages: {sd['n_passage_seeds_nonzero']} of {sd['n_passages']} seeded, weight = dense x {cfg['passage_node_weight']}; top 5:"))
        for x in sd["passage_seeds_top10"][:5]:
            say(f"  passage  {x['reset_weight']:.4f}  {gold(x['gold'])} {x['title']}")
        stop()
        say(s.cyan(f"\n[4] Personalized PageRank (damping {cfg['damping']}): top 10 nodes"))
        for x in t["step4_ppr_top10"]:
            say(f"  {x['rank']:>2}. {x['score']:.5f}  {x['type']:<7} {gold(x['gold'])} {x['label']}")
        stop()
    say(s.cyan("\n[5] final top 5 passages            vs  dense top 5"))
    for h, d in zip(t["step5_top5"], t["dense_top5"]):
        say(f"  {h['rank']}. {gold(h['gold'])} {h['title'][:34]:<34}  {gold(d['gold'])} {d['title'][:34]}")
    r = t["recall_at_5"]
    say(f"  Recall@5: HippoRAG {r['hipporag']:.2f}   dense {r['dense']:.2f}")
    stop()
    if t["step6_reader"]:
        rd = t["step6_reader"]
        say(s.cyan("\n[6] reader (gpt-4o-mini on the top 5)"))
        say(f"  answer: {s.bold(rd['answer'])}")
        say(f"  gold:   {' / '.join(rd['gold_answers'])}    F1 {rd['F1']:.2f}  EM {rd['EM']:.0f}")
    rec = t["recorded_n500_run"]
    say(s.dim(f"\nrecorded n=500 run: answer {rec['hipporag_answer']!r}; same top 5 as this trace: {rec['live_top5_equals_recorded']}"))
    if t.get("cost"):
        c = t["cost"]
        say(s.dim(f"cost of this run: {c['llm_paid_calls']} paid LLM call(s), {c['embedding_texts']} query embedding(s), ~Rs {c['inr_estimate']:.4f}"))


def render_markdown(t):
    fact_str = lambda f: "(" + " \\| ".join(f) + ")"   # escaped: a bare | would split the table cell
    cfg = t["config"]
    g = lambda b: "**gold**" if b else ""
    L = [f"# Trace: MuSiQue question {t['index']}", "",
         f"**Question.** {t['question']}", "",
         f"**Gold answer.** {' / '.join(t['gold_answers'])}  ",
         f"**Gold passages.** {' ; '.join(t['gold_titles'])}", "",
         f"Source: `demo/traces/q{t['index']}.json` (written by `demo/run_demo.py --live --save --q {t['index']}` at "
         f"{t['meta']['generated']}, commit `{t['meta']['commit']}`, src/ + main.py identical to upstream-base: "
         f"{t['meta']['src_main_identical_to_upstream_base']}). Index: {t['meta']['index']}; graph "
         f"{t['meta']['graph']['nodes']} nodes, {t['meta']['graph']['edges']} edges. Settings: damping {cfg['damping']}, "
         f"passage_node_weight {cfg['passage_node_weight']}, linking_top_k {cfg['linking_top_k']}, qa_top_k {cfg['qa_top_k']}.", "",
         "## 1. Query → triple (top 5 by min-max-normalized cosine)", "", "| rank | score | fact |", "|---|---|---|"]
    L += [f"| {x['rank']} | {x['score']:.4f} | {fact_str(x['fact'])} |" for x in t["step1_query_to_triple"]]
    f = t["step2_filter"]
    L += ["", "## 2. Recognition-memory filter (gpt-4o-mini)", "", f"Input {len(f['input'])} facts, output {len(f['output'])}."
          + (" No fact kept: falls back to dense retrieval." if f["fallback_to_dense"] else ""), "", "| fact | filter |", "|---|---|"]
    L += [f"| {fact_str(x)} | {'kept' if x in f['output'] else 'removed'} |" for x in f["input"]]
    if t["step3_seeds"]:
        sd = t["step3_seeds"]
        L += ["", "## 3. Seed nodes (PPR reset vector)", "",
              f"Reset mass: phrases {sd['phrase_mass']:.4f} ({sd['phrase_share']:.1%}), passages {sd['passage_mass']:.4f} "
              f"({sd['passage_share']:.1%}); {sd['n_passage_seeds_nonzero']} of {sd['n_passages']} passages have weight > 0. "
              f"Rule: {sd['rule']}.", "", "| entity seed | reset weight | share | passages containing it |", "|---|---|---|---|"]
        L += [f"| {x['entity']} | {x['reset_weight']:.5f} | {x['share_of_reset']:.1%} | {x['n_passages_with_entity']} |" for x in sd["phrase_seeds"]]
        L += ["", f"Top 10 passage seeds (weight = min-max dense score × {cfg['passage_node_weight']}):", "",
              "| passage | dense (min-max) | reset weight | gold |", "|---|---|---|---|"]
        L += [f"| {x['title']} | {x['dense_score_minmax']:.4f} | {x['reset_weight']:.5f} | {g(x['gold'])} |" for x in sd["passage_seeds_top10"]]
        L += ["", f"## 4. Personalized PageRank, top 10 nodes (damping {cfg['damping']})", "", t["step4_check"] + ".", "",
              "| rank | node | type | PPR score | reset weight | gold |", "|---|---|---|---|---|---|"]
        L += [f"| {x['rank']} | {x['label']} | {x['type']} | {x['score']:.6f} | {x['reset_weight']:.5f} | {g(x['gold'])} |" for x in t["step4_ppr_top10"]]
    L += ["", "## 5. Final top 5 passages (HippoRAG 2) vs dense", "", "| rank | HippoRAG 2 | score | dense | score |", "|---|---|---|---|---|"]
    L += [f"| {h['rank']} | {h['title']} {g(h['gold'])} | {h['score']:.6f} | {d['title']} {g(d['gold'])} | {d['score']:.4f} |"
          for h, d in zip(t["step5_top5"], t["dense_top5"])]
    r = t["recall_at_5"]
    L += ["", f"Recall@5 for this question: HippoRAG 2 {r['hipporag']:.2f}, dense {r['dense']:.2f}."]
    if t["step6_reader"]:
        rd = t["step6_reader"]
        L += ["", "## 6. Reader (gpt-4o-mini on the HippoRAG 2 top 5)", "", "| | |", "|---|---|",
              f"| reader answer | {rd['answer']} |", f"| gold answer | {' / '.join(rd['gold_answers'])} |",
              f"| token F1 / EM | {rd['F1']:.2f} / {rd['EM']:.0f} |", "", "Raw reader response:", "", "```", rd["raw_response"].strip(), "```"]
    rec = t["recorded_n500_run"]
    L += ["", "## Recorded n = 500 run (for comparison)", "", f"Source: {rec['source']}.", "",
          f"- HippoRAG 2 answer: {rec['hipporag_answer']}", f"- dense answer: {rec['dense_answer']}",
          f"- HippoRAG 2 top 5: {' ; '.join(rec['hipporag_top5'])}", f"- dense top 5: {' ; '.join(rec['dense_top5'])}",
          f"- this trace's top 5 equals the recorded top 5: {rec['live_top5_equals_recorded']}"]
    if t.get("cost"):
        c = t["cost"]
        L += ["", "## Cost of generating this trace", "",
              f"{c['llm_paid_calls']} paid LLM call(s) ({c['llm_paid_tokens_in']} in / {c['llm_paid_tokens_out']} out tokens), "
              f"{len(c['llm_calls']) - c['llm_paid_calls']} LLM cache hit(s), {c['embedding_texts']} query embedding(s) "
              f"(~{c['embedding_tokens_tiktoken']} tokens): ≈ ₹{c['inr_estimate']:.4f} ({c['pricing']})."]
    return "\n".join(L) + "\n"


# ---- graph statistics ----------------------------------------------------------------------------------
def graph_stats_markdown():
    import collections
    import hashlib
    import pickle
    path = INDEX_SAVE_DIR / WORKING_DIR_NAME / "graph.pickle"
    raw = path.read_bytes()
    g = pickle.loads(raw)
    names = g.vs["name"]
    node_types = collections.Counter("passage" if n.startswith("chunk-") else "entity" if n.startswith("entity-") else "other" for n in names)
    edge_kinds = collections.Counter(g.es["edge_kind"])
    ends = collections.Counter()
    for e in g.es:
        a, b = names[e.source].split("-")[0], names[e.target].split("-")[0]
        ends[" – ".join(sorted((a, b)))] += 1
    deg = np.asarray(g.degree())
    is_ent = np.asarray([n.startswith("entity-") for n in names])
    ent_psg = collections.Counter()
    for e in g.es.select(edge_kind_eq="passage") if "passage" in edge_kinds else []:
        a, b = e.source, e.target
        ent_psg[a if is_ent[a] else b] += 1
    single = sum(1 for v in np.where(is_ent)[0] if ent_psg.get(int(v), 0) == 1)
    L = ["# Graph statistics: HippoRAG 2 index, MuSiQue (11,656-passage corpus)", "",
         f"Source: `{path.relative_to(REPO_ROOT)}` (APFS clone of `outputs/hipporag_n500_musique/{WORKING_DIR_NAME}/graph.pickle`), "
         f"sha256 `{hashlib.sha256(raw).hexdigest()[:16]}…`. Written by `.venv/bin/python demo/run_demo.py --graph_stats` (offline). "
         "The graph is undirected (`is_directed() = " + str(g.is_directed()) + "`); PPR also runs with `directed=False`.", "",
         "## Nodes", "", "| type | count |", "|---|---|"]
    L += [f"| {k} | {v:,} |" for k, v in sorted(node_types.items())] + [f"| **total** | **{g.vcount():,}** |", ""]
    L += ["## Edges by `edge_kind`", "", "| edge_kind | count |", "|---|---|"]
    L += [f"| {k} | {v:,} |" for k, v in sorted(edge_kinds.items())] + [f"| **total** | **{g.ecount():,}** |", ""]
    L += ["## Edges by endpoint types", "", "| endpoints | count |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in sorted(ends.items())]
    L += ["", "## Degree", "", "| node type | mean degree | median | max |", "|---|---|---|---|",
          f"| entity | {deg[is_ent].mean():.2f} | {np.median(deg[is_ent]):.0f} | {deg[is_ent].max()} |",
          f"| passage | {deg[~is_ent].mean():.2f} | {np.median(deg[~is_ent]):.0f} | {deg[~is_ent].max()} |"]
    if ent_psg:
        L += ["", f"Entities linked to exactly one passage (passage edges): {single:,} of {int(is_ent.sum()):,} "
              f"({single / is_ent.sum():.1%})."]
    return "\n".join(L) + "\n"
