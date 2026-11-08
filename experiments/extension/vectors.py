"""Embed once, reuse everywhere.

Embeddings are not bit-identical across API calls, so every injected passage, new fact, new entity and
target question is embedded exactly once (embed_once, the only paid step in this file) and stored in a
VectorTable. Cells never call the embedding API: their stores and HippoRAG itself get a FrozenEmbedder,
a strict lookup that raises on any text it was not given. Zero embedding calls per cell is therefore
enforced, not hoped for.

The calls mirror upstream exactly, so vectors match what HippoRAG would have computed itself:
  passages / facts / entities: EmbeddingStore.insert_strings -> batch_encode(texts)  (norm = config default)
  queries: get_query_embeddings with query_instruction_mode 'ignored' (OpenAI) -> batch_encode(queries, norm=True)

CLI (paid when run without --dry-run; needs the key in the environment):
    .venv/bin/python experiments/extension/vectors.py --out <path>/vectors.npz --dry-run
    .venv/bin/python experiments/extension/vectors.py --out <path>/vectors.npz --confirm-paid
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import (BASE_WORKING_DIR, PRICE_USD_PER_M, TARGETS_PATH, capture_config,  # noqa: E402
                                          inr, text_processing)
from experiments.extension.inject import all_variants  # noqa: E402

KINDS = ("chunk", "fact", "entity", "query")


class FrozenEmbedder:
    """Stand-in embedding model: returns stored vectors, raises KeyError on anything else."""

    query_instruction_mode = "ignored"   # same as OpenAIEmbeddingModel, so HippoRAG uses one query vector

    def __init__(self, table: "VectorTable"):
        self.table = table
        self.calls = 0
        self.texts_served = 0

    def batch_encode(self, texts, **kwargs):
        if isinstance(texts, str):
            texts = [texts]
        if kwargs.get("instruction"):
            raise ValueError("FrozenEmbedder: an instruction was requested; OpenAI vectors are instruction-free")
        missing = [t for t in texts if t not in self.table]
        if missing:
            raise KeyError(f"FrozenEmbedder: {len(missing)} text(s) have no precomputed vector, e.g. {missing[0][:120]!r}")
        self.calls += 1
        self.texts_served += len(texts)
        return np.stack([self.table[t] for t in texts]).astype(np.float32)


class VectorTable:
    def __init__(self, vectors=None, kinds=None):
        self.vectors = dict(vectors or {})
        self.kinds = dict(kinds or {})

    def __contains__(self, text):
        return text in self.vectors

    def __getitem__(self, text):
        return self.vectors[text]

    def __len__(self):
        return len(self.vectors)

    def add(self, kind, texts, vecs):
        vecs = np.asarray(vecs, dtype=np.float32)
        if vecs.shape[0] != len(texts):
            raise ValueError("texts/vectors length mismatch")
        for text, vec in zip(texts, vecs):
            if text in self.vectors:
                raise ValueError(f"vector for {text[:80]!r} already present; embeddings must be computed once")
            self.vectors[text] = vec
            self.kinds[text] = kind

    def save(self, path):
        texts = list(self.vectors)
        np.savez(path, texts=np.array(texts, dtype=object), kinds=np.array([self.kinds[t] for t in texts], dtype=object),
                 vecs=np.stack([self.vectors[t] for t in texts]) if texts else np.zeros((0, 0), np.float32))

    @classmethod
    def load(cls, path):
        data = np.load(path, allow_pickle=True)
        texts, kinds = list(data["texts"]), list(data["kinds"])
        return cls(dict(zip(texts, data["vecs"])), dict(zip(texts, kinds)))


def fact_strings(triples):
    """Fact-store texts for raw triples, exactly as HippoRAG.index builds them."""
    return [str(tuple(text_processing(list(t)))) for t in triples if len(t) == 3]


def entity_strings(triples):
    return [e for t in triples if len(t) == 3 for e in (text_processing(t[0]), text_processing(t[2]))]


def store_ids(working_dir, namespace):
    """Hash IDs in one of the base index's parquet stores (hash_id column only; vectors not loaded)."""
    path = Path(working_dir) / f"{namespace}_embeddings" / f"vdb_{namespace}.parquet"
    return set(pd.read_parquet(path, columns=["hash_id"])["hash_id"])


def plan_texts(targets, base_ids):
    """{kind: [texts]} still missing from the base stores for the whole grid. base_ids: {namespace: set(hash_ids)}."""
    from src.hipporag.embedding_store import compute_mdhash_id
    variants = all_variants(targets)
    plan = {kind: [] for kind in KINDS}
    seen = set()

    def want(kind, text):
        if text not in seen and compute_mdhash_id(text, prefix=kind + "-") not in base_ids.get(kind, set()):
            seen.add(text)
            plan[kind].append(text)

    for v in variants:
        want("chunk", v["content"])
        for f in fact_strings(v["triples"]):
            want("fact", f)
        for e in entity_strings(v["triples"]):
            want("entity", e)
    for t in targets:
        if t["question"] not in seen:
            seen.add(t["question"])
            plan["query"].append(t["question"])
    return plan


def embed_plan(plan, model, batch_size=128):
    table = VectorTable()
    for kind in KINDS:
        texts = plan[kind]
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            vecs = model.batch_encode(batch, norm=True) if kind == "query" else model.batch_encode(batch)
            table.add(kind, batch, vecs)
    return table


def count_tokens(texts):
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")   # text-embedding-3-* tokenizer
    return sum(len(enc.encode(t)) for t in texts)


def load_targets(path=TARGETS_PATH):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets", default=str(TARGETS_PATH))
    parser.add_argument("--out", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--confirm-paid", action="store_true")
    args = parser.parse_args()

    targets = load_targets(args.targets)
    base_ids = {ns: store_ids(BASE_WORKING_DIR, ns) for ns in ("chunk", "fact", "entity")}
    plan = plan_texts(targets, base_ids)
    tokens = {kind: count_tokens(texts) for kind, texts in plan.items()}
    total = sum(tokens.values())
    usd = total / 1e6 * PRICE_USD_PER_M["text-embedding-3-small"]
    for kind in KINDS:
        print(f"{kind:7s} texts={len(plan[kind]):5d} tokens={tokens[kind]:8d}")
    print(f"total tokens={total}  est. ${usd:.4f} = Rs {inr(usd):.3f} (1.1x list, Rs88/$)")
    if args.dry_run:
        return
    if Path(args.out).exists():
        sys.exit(f"{args.out} exists; vectors are computed once. Refusing to overwrite.")
    from src.hipporag.HippoRAG import _get_embedding_model_class
    config = capture_config("/nonexistent/embed_once")   # config only; nothing is written for it
    model = _get_embedding_model_class(embedding_model_name=config.embedding_model_name,
                                       provider=config.embedding_provider)(global_config=config,
                                                                           embedding_model_name=config.embedding_model_name)
    table = embed_plan(plan, model, batch_size=config.embedding_batch_size)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    table.save(args.out)
    print(f"wrote {len(table)} vectors to {args.out}")


if __name__ == "__main__":
    main()
