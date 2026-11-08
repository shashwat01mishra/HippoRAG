"""Step 7: grid runner.  n in {1,3} x k in {0,1,2,3,5}, all targets injected into ONE index per cell.

Modes
  --dry-run            offline. Per cell: embedding lookups (all served from the frozen table; 0 API calls),
                       filter calls (new vs LLM-cache hits), reader calls, estimated Rs, disk, wall time.
  --measure DIR        offline rehearsal on the REAL base index: clone into DIR (APFS clone), inject cell
                       n=3,k=5 with random stand-in vectors, run experiments/verify_openie_cache.py on it,
                       index, then time attribution for every target with a fake filter (network blocked).
                       Writes a JSON of measurements that --dry-run can use (--timings). DIR is deleted after.
  --confirm-paid       the real run (filter calls and, with --long_context, reader calls are paid).

Filter-call cache reuse (structural, so exact): the filter prompt is a function of the question and the top-5
candidate facts, which depend only on the frozen query vector, the fact set and the fact vectors. Old copies
add no facts, so both k=0 cells share one fact set (the base's), and all eight k>=1 cells share another
(base + every target's (s, r, o')). Every cell's llm_cache is a symlink to one shared cache, so each question
pays for at most 2 filter calls over the whole grid. The fix arm reuses the same prompts (cache hits).

Run from the repo root:
    .venv/bin/python experiments/extension/run_cells.py --dry-run [--timings T.json] [--long_context]
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension import inject, long_context, vectors  # noqa: E402
from experiments.extension.common import (BASE_SAVE_DIR, BASE_WORKING_DIR, DATASET_DIR, PRICE_USD_PER_M,  # noqa: E402
                                          REPO_ROOT, TARGETS_PATH, WORKING_DIR_NAME, capture_config, chunk_text, inr)

CELLS = [(n, k) for n in inject.N_GRID for k in inject.K_GRID]

# Empirical per-call figures (read-only from outputs/hipporag_n500_musique/llm_cache, 500 filter / 502 QA rows):
FILTER_IN, FILTER_OUT = 2836, 54
READER_OUT = 95
# Latency per uncached call, from the n=500 logs: dense 15 min / 400 new questions = 2.25 s (one QA call);
# HippoRAG 26 min / 400 = 3.9 s (filter + QA), so filter ~ 1.65 s.
FILTER_SECONDS, READER_SECONDS = 1.65, 2.25


def cell_prefix(root, n, k):
    return Path(root) / f"cell_n{n}_k{k}"          # run_subset/capture_config append _musique


def load_samples():
    return json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))


def ids_for(target, sample, variants):
    from src.hipporag.embedding_store import compute_mdhash_id
    mine = [v for v in variants if v["target_id"] == target["target_id"]]
    old = [compute_mdhash_id(target["gold_chunk"], "chunk-")] + [v["chunk_id"] for v in mine if v["role"] == "old"]
    new = [v["chunk_id"] for v in mine if v["role"] == "new"]
    gold_other = {compute_mdhash_id(chunk_text(p["title"], p["paragraph_text"]), "chunk-")
                  for p in sample["paragraphs"] if p["is_supporting"]} - set(old)
    return old, new, gold_other


def filter_plan(n_targets):
    """Per cell: (new filter calls, cache hits incl. the fix arm's repeat)."""
    seen, out = set(), {}
    for n, k in CELLS:
        cls = "k0" if k == 0 else "k>=1"
        new = 0 if cls in seen else n_targets
        seen.add(cls)
        out[(n, k)] = (new, 2 * n_targets - new)     # two arms (no-fix, fix) per question
    return out


def reader_tokens(targets, samples):
    """Exact prompt tokens (o200k_base, gpt-4o-mini) of every long-context reader prompt, per cell."""
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    per_cell = {}
    for n, k in CELLS:
        total = 0
        for t in targets:
            msgs = long_context.build_messages(samples[t["sample_index"]], t, n, k)
            total += sum(len(enc.encode(m["content"])) + 4 for m in msgs) + 3
        per_cell[(n, k)] = total
    return per_cell


def calibrate_reader_tokens():
    """Same counter applied to the n=500 HippoRAG QA prompts vs the API's mean prompt_tokens (1,441)."""
    import tiktoken
    from src.hipporag.prompts.prompt_template_manager import PromptTemplateManager
    enc = tiktoken.get_encoding("o200k_base")
    ptm = PromptTemplateManager(role_mapping={"system": "system", "user": "user", "assistant": "assistant"})
    rows = json.loads((REPO_ROOT / "outputs" / "hipporag_n500_musique" / "per_query_n500.json").read_text(encoding="utf-8"))
    counts = []
    for r in rows:
        prompt_user = "".join(f"Wikipedia Title: {p}\n\n" for p in r["docs"][:5]) + "Question: " + r["question"] + "\nThought: "
        msgs = ptm.render(name="rag_qa_musique", prompt_user=prompt_user)
        counts.append(sum(len(enc.encode(m["content"])) + 4 for m in msgs) + 3)
    return float(np.mean(counts))


def disk_plan(timings):
    """Real (non-shared) bytes per cell: files a cell rewrites; everything else stays block-shared with the base."""
    size = lambda p: os.path.getsize(p)
    wd = BASE_WORKING_DIR
    state = size(wd / "openie_state.json")
    results = size(BASE_SAVE_DIR / "openie_results_ner_gpt-4o-mini.json")
    chunks = size(wd / "chunk_embeddings" / "vdb_chunk.parquet")
    facts = size(wd / "fact_embeddings" / "vdb_fact.parquet")
    graph = size(wd / "graph.pickle")
    meta = size(wd / "chunk_metadata.json")
    out = {}
    for n, k in CELLS:
        b = state                                                  # injected OpenIE rows appended (rewrite)
        if n > 1 or k > 0:
            b += results + chunks + graph + meta                   # index(): stores, graph, metadata rewritten
        if k > 0:
            b += facts                                             # new (s, r, o') facts -> fact store rewritten
        out[(n, k)] = b
    return out


def dry_run(args):
    targets = vectors.load_targets(args.targets)
    samples = load_samples()
    T = len(targets)
    base_ids = {ns: vectors.store_ids(BASE_WORKING_DIR, ns) for ns in ("chunk", "fact", "entity")}
    plan = vectors.plan_texts(targets, base_ids)
    emb_tokens = sum(vectors.count_tokens(v) for v in plan.values())
    emb_usd = emb_tokens / 1e6 * PRICE_USD_PER_M["text-embedding-3-small"]
    fplan = filter_plan(T)
    rtok = reader_tokens(targets, samples)
    disk = disk_plan(None)
    timings = json.loads(Path(args.timings).read_text()) if args.timings else None
    new_facts = len(plan["fact"])

    print(f"targets={T}  frozen vectors to embed once: " + ", ".join(f"{k}={len(v)}" for k, v in plan.items())
          + f"  ({emb_tokens} tokens, Rs {inr(emb_usd):.3f})")
    print(f"reader token count check: n=500 QA prompts counted {calibrate_reader_tokens():.0f} vs API mean 1441")
    hdr = (f"{'cell':9s} {'inj':>4s} {'emb API':>7s} {'emb lookups':>11s} {'filter new':>10s} {'cache hits':>10s} "
           f"{'Rs filter':>9s} {'reader':>6s} {'reader tok':>10s} {'Rs reader':>9s} {'disk GB':>7s} {'wall min':>8s}")
    print(hdr)
    tot = {"rf": 0.0, "rr": 0.0, "disk": 0, "wall": 0.0, "wall_lc": 0.0, "fnew": 0, "reader": 0}
    for n, k in CELLS:
        inj = T * ((n - 1) + k)
        lookups = inj + (new_facts if k > 0 else 0) + T          # chunks + new facts + preloaded queries
        fnew, fhit = fplan[(n, k)]
        usd_f = fnew * (FILTER_IN * PRICE_USD_PER_M["gpt-4o-mini_in"] + FILTER_OUT * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
        usd_r = (rtok[(n, k)] * PRICE_USD_PER_M["gpt-4o-mini_in"] + T * READER_OUT * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
        if timings:
            build = timings["clone_s"] + timings["verify_s"] + (timings["index_s"] if inj else 0) + timings["load_s"] + timings["prepare_s"]
            compute = 2 * T * timings["per_query_s"]
        else:
            build, compute = float("nan"), float("nan")
        wall = (build + compute + fnew * FILTER_SECONDS) / 60
        wall_lc = T * READER_SECONDS / 60
        print(f"n={n},k={k:<3d} {inj:4d} {0:7d} {lookups:11d} {fnew:10d} {fhit:10d} {inr(usd_f):9.2f} {T:6d} "
              f"{rtok[(n, k)]:10d} {inr(usd_r):9.2f} {disk[(n, k)] / 1e9:7.2f} {wall:8.1f}")
        tot["rf"] += inr(usd_f); tot["rr"] += inr(usd_r); tot["disk"] += disk[(n, k)]
        tot["wall"] += wall; tot["wall_lc"] += wall_lc; tot["fnew"] += fnew; tot["reader"] += T
    print(f"TOTAL: filter calls {tot['fnew']} (Rs {tot['rf']:.2f}); embed-once Rs {inr(emb_usd):.3f}; "
          f"grid without long-context Rs {tot['rf'] + inr(emb_usd):.2f}; reader calls {tot['reader']} (Rs {tot['rr']:.2f}); "
          f"with long-context Rs {tot['rf'] + tot['rr'] + inr(emb_usd):.2f}")
    print(f"disk (non-shared, all cells kept): {tot['disk'] / 1e9:.1f} GB; wall: {tot['wall']:.0f} min retrieval grid "
          f"+ {tot['wall_lc']:.0f} min long-context")
    print("Rs = list price x 1.1 at Rs 88/$. Filter tokens/latency from the n=500 run; reader tokens counted exactly.")


def _block_network():
    def blocked(*a, **k):
        raise RuntimeError("network blocked (offline measurement)")
    socket.socket.connect = blocked
    socket.create_connection = blocked
    os.environ["OPENAI_API_KEY"] = "sk-offline-placeholder"
    os.environ.pop("OPENAI_BASE_URL", None)


class _KeepTopTwo:
    """Offline stand-in for the filter LLM: keeps the first two candidate facts."""

    def infer(self, messages, **kwargs):
        last = messages[-1]["content"]
        facts = json.loads(last.split("[[ ## fact_before_filter ## ]]\n")[1].split("\n\nRespond")[0])
        facts["fact"] = facts["fact"][:2]
        return f"[[ ## fact_after_filter ## ]]\n{json.dumps(facts)}\n\n[[ ## completed ## ]]", {}, False


def measure(args):
    _block_network()
    from experiments.extension.attrib_rag import AttributionHippoRAG
    from experiments.extension.cell_index import clone_base, index_cell, remove_cell
    from experiments.extension.inject import append_openie_rows
    targets = vectors.load_targets(args.targets)
    samples = load_samples()
    n, k = 3, 5
    root = Path(args.measure)
    prefix = cell_prefix(root, n, k)
    save_dir = Path(str(prefix) + "_musique")
    variants = inject.cell_variants(targets, n, k)
    out = {"cell": [n, k], "targets": len(targets), "injected": len(variants)}
    try:
        t0 = time.time()
        clone_base(BASE_SAVE_DIR, save_dir, shared_cache_dir=root / "llm_cache_shared")
        out["clone_s"] = time.time() - t0
        inodes = _inodes(save_dir)
        appended = append_openie_rows(save_dir / WORKING_DIR_NAME / "openie_state.json", inject.openie_rows(variants))
        out["openie_rows_appended"] = appended

        extra = root / "extra_docs.json"
        extra.write_text(json.dumps([v["content"] for v in variants]), encoding="utf-8")
        t0 = time.time()
        proc = subprocess.run([sys.executable, "experiments/verify_openie_cache.py", "--extra_docs", str(extra), "--",
                               *capture_args(prefix)], cwd=REPO_ROOT, capture_output=True, text=True)
        out["verify_s"] = time.time() - t0
        out["verify_exit"] = proc.returncode
        out["verify_output"] = [l for l in proc.stdout.splitlines() if "=" in l]

        base_ids = {ns: vectors.store_ids(BASE_WORKING_DIR, ns) for ns in ("chunk", "fact", "entity")}
        plan = vectors.plan_texts(targets, base_ids)
        rng = np.random.default_rng(0)
        table = vectors.VectorTable()
        for kind, texts in plan.items():
            v = rng.standard_normal((len(texts), 1536)).astype(np.float32)
            table.add(kind, texts, v / np.linalg.norm(v, axis=1, keepdims=True))
        frozen = vectors.FrozenEmbedder(table)

        t0 = time.time()
        rag = AttributionHippoRAG(global_config=capture_config(str(prefix)))
        out["load_s"] = time.time() - t0
        rag.install_frozen_embedder(frozen)
        rag.rerank_filter.llm_infer_fn = _KeepTopTwo().infer
        t0 = time.time()
        out["index_stats"] = index_cell(rag, variants, frozen)
        out["index_s"] = time.time() - t0
        t0 = time.time()
        rag.preload_query_vectors(table, [t["question"] for t in targets])
        out["prepare_s"] = time.time() - t0
        t0 = time.time()
        sample_rec = None
        for t in targets:
            old, new, gold_other = ids_for(t, samples[t["sample_index"]], variants)
            for fix in (False, True):
                rag.apply_fix = fix
                rec = rag.attribute(t, old, new, gold_other, injected_ids={v["chunk_id"] for v in variants})
                sample_rec = sample_rec or rec
        out["per_query_s"] = (time.time() - t0) / (2 * len(targets))
        out["embed_api_calls"] = 0
        out["frozen_lookups"] = frozen.calls
        rag.close()
        # real (non-shared) bytes: files rewritten after the clone
        after = _inodes(save_dir)
        rewritten = {rel: size for rel, (ino, size) in after.items() if inodes.get(rel, (None,))[0] != ino and size > 0}
        out["rewritten_files"] = rewritten
        out["rewritten_bytes"] = sum(rewritten.values())
        out["sample_record_keys"] = sorted(sample_rec)
    finally:
        if save_dir.exists():
            remove_cell(save_dir)
    Path(args.timings_out).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))


def _inodes(root):
    """{relative path: (inode, size)}. A clone shares blocks until rewritten; upstream rewrites via os.replace (new inode)."""
    return {str(p.relative_to(root)): (p.stat().st_ino, p.stat().st_size)
            for p in Path(root).rglob("*") if p.is_file() and not p.is_symlink() and "llm_cache" not in p.parts}


def capture_args(prefix):
    from experiments.extension.common import launch_args
    return launch_args(str(prefix))


def run(args):
    """The paid run. Requires the frozen vectors file and --confirm-paid."""
    from experiments.extension.attrib_rag import AttributionHippoRAG
    from experiments.extension.cell_index import index_cell, prepare_cell
    targets = vectors.load_targets(args.targets)
    samples = load_samples()
    table = vectors.VectorTable.load(args.vectors)
    root = Path(args.root)
    shared_cache = root / "llm_cache_shared"
    (root / "results").mkdir(parents=True, exist_ok=True)
    cells = [tuple(map(int, c.split(","))) for c in args.cells] if args.cells else CELLS
    for n, k in cells:
        prefix = cell_prefix(root, n, k)
        save_dir = Path(str(prefix) + "_musique")
        variants = inject.cell_variants(targets, n, k)
        prepare_cell(BASE_SAVE_DIR, save_dir, WORKING_DIR_NAME, variants, shared_cache)
        extra = root / f"extra_docs_n{n}_k{k}.json"
        extra.write_text(json.dumps([v["content"] for v in variants]), encoding="utf-8")
        guard = subprocess.run([sys.executable, "experiments/verify_openie_cache.py", "--extra_docs", str(extra), "--",
                                *capture_args(prefix)], cwd=REPO_ROOT, capture_output=True, text=True)
        print(guard.stdout)
        if guard.returncode != 0:
            sys.exit(f"ABORT n={n},k={k}: OpenIE guard failed")
        frozen = vectors.FrozenEmbedder(table)
        with AttributionHippoRAG(global_config=capture_config(str(prefix))) as rag:
            rag.install_frozen_embedder(frozen)
            calls = {"filter_new": 0, "filter_hit": 0}
            infer = rag.rerank_filter.llm_infer_fn

            def counting_infer(*a, **kw):
                res = infer(*a, **kw)
                calls["filter_hit" if res[2] else "filter_new"] += 1
                return res
            rag.rerank_filter.llm_infer_fn = counting_infer
            stats = index_cell(rag, variants, frozen)
            rag.preload_query_vectors(table, [t["question"] for t in targets])
            injected = {v["chunk_id"] for v in variants}
            out_path = root / "results" / f"cell_n{n}_k{k}.jsonl"
            with open(out_path, "w", encoding="utf-8") as f:
                for t in targets:
                    old, new, gold_other = ids_for(t, samples[t["sample_index"]], variants)
                    for fix in (False, True):
                        rag.apply_fix = fix
                        rec = rag.attribute(t, old, new, gold_other, injected, tolerance=args.tolerance)
                        rec.update(cell=[n, k])
                        f.write(json.dumps(rec, ensure_ascii=False, default=float) + "\n")
                    if args.long_context:
                        msgs = long_context.build_messages(samples[t["sample_index"]], t, n, k)
                        resp, meta, hit = rag.qa_llm.infer(msgs)
                        ans = long_context.parse_answer(resp)
                        f.write(json.dumps({"target_id": t["target_id"], "cell": [n, k], "arm": "long_context",
                                            "answer": ans, "label": long_context.classify(ans, t["o"], t["o_prime"], t["answer_aliases"]),
                                            "cache_hit": hit, "usage": meta}, ensure_ascii=False) + "\n")
        print(f"n={n},k={k}: index {stats}; filter calls {calls}; embedding API calls 0 (frozen lookups {frozen.calls}) -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets", default=str(TARGETS_PATH))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--measure", metavar="DIR")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--timings", help="JSON written by --measure, used by --dry-run for wall time")
    parser.add_argument("--timings_out", default="measure.json")
    parser.add_argument("--root", help="paid run: root dir for cell save dirs, shared LLM cache and results")
    parser.add_argument("--vectors", help="paid run: frozen vectors .npz from vectors.py")
    parser.add_argument("--cells", nargs="*", help="paid run: subset like 1,0 3,5 (default: all 10)")
    parser.add_argument("--long_context", action="store_true", help="paid run: also run the long-context reader")
    parser.add_argument("--tolerance", type=float, default=0.01, help="relative near-tie tolerance")
    args = parser.parse_args()
    if args.dry_run:
        dry_run(args)
    elif args.measure:
        measure(args)
    else:
        if not (args.root and args.vectors):
            sys.exit("--confirm-paid needs --root and --vectors")
        run(args)


if __name__ == "__main__":
    main()
