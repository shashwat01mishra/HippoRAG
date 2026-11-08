"""Step 2: deterministic injection (no LLM).

For a target and a grid cell (n, k):
  old support n: the base gold passage (already in the index) plus n-1 extra old copies;
  corrections k: k copies of the swapped passage (o -> o' in body and in the cached triples).

Every injected variant differs from the others only in its title line, so the MD5 chunk IDs differ while
the triples are exactly those of the gold (old) or swapped (new) passage. A variant's text is a function
of (target, role, j) only, never of n or k, so the same variant is byte-identical in every cell it appears
in and its embedding can be computed once and reused.

Insertion order within a cell is recorded in chunk metadata: old copies first, then corrections,
in target order. The base corpus has no metadata and counts as insert_seq 0 (oldest).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import chunk_text  # noqa: E402
from src.hipporag.embedding_store import compute_mdhash_id  # noqa: E402
from src.hipporag.utils.misc_utils import Chunk  # noqa: E402

N_GRID = (1, 3)
K_GRID = (0, 1, 2, 3, 5)


def variant_tag(target_id: str, role: str, j: int) -> str:
    """Neutral, order-free 4-hex tag. role is 'old' or 'new'. DESIGN DECISION: title-line format."""
    return hashlib.md5(f"{target_id}|{role}|{j}".encode()).hexdigest()[:4]


def variant_title(title: str, target_id: str, role: str, j: int) -> str:
    return f"{title} ({variant_tag(target_id, role, j)})"


def make_variant(target: dict, role: str, j: int) -> dict:
    """role='old', j>=2: extra old copy j.  role='new', j>=1: correction j."""
    if role == "old":
        if j < 2:
            raise ValueError("old copy 1 is the base gold passage; extra copies start at j=2")
        body, triples, entities = target["body"], target["triples"], target["entities"]
    elif role == "new":
        if j < 1:
            raise ValueError("corrections start at j=1")
        body, triples, entities = target["swapped_body"], target["swapped_triples"], target["swapped_entities"]
    else:
        raise ValueError(role)
    title = variant_title(target["title"], target["target_id"], role, j)
    content = chunk_text(title, body)
    return {"target_id": target["target_id"], "role": role, "j": j, "title": title, "body": body,
            "content": content, "chunk_id": compute_mdhash_id(content, prefix="chunk-"),
            "triples": [list(t) for t in triples], "entities": list(entities)}


def cell_variants(targets, n: int, k: int):
    """All injected variants for one cell, in insertion order, with insert_seq starting at 1."""
    out = []
    for role, js in (("old", range(2, n + 1)), ("new", range(1, k + 1))):
        for target in targets:
            for j in js:
                out.append(make_variant(target, role, j))
    for seq, v in enumerate(out, start=1):
        v["insert_seq"] = seq
    return out


def all_variants(targets, n_max=max(N_GRID), k_max=max(K_GRID)):
    """The union of variants over the whole grid (what needs embedding once)."""
    return cell_variants(targets, n_max, k_max)


def as_chunks(variants):
    """HippoRAG input: Chunk objects whose metadata lands in the cell's chunk_metadata.json."""
    return [Chunk(content=v["content"], metadata={"target_id": v["target_id"], "role": v["role"], "j": v["j"],
                                                   "insert_seq": v["insert_seq"]}) for v in variants]


def openie_rows(variants):
    """OpenIE-state rows for the variants, in the shape load_existing_openie expects."""
    return [{"idx": v["chunk_id"], "title": v["title"], "text": v["body"], "passage": v["content"],
             "extracted_entities": v["entities"], "extracted_triples": v["triples"]} for v in variants]


def append_openie_rows(openie_state_path, rows):
    """Append rows to a cell's openie_state.json, keeping its provenance block unchanged.

    The provenance is the stamp the base index was built with, so loading the cell validates exactly
    as the base did and load_existing_openie finds every injected chunk already extracted.
    """
    path = Path(openie_state_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("provenance"):
        raise ValueError(f"{path} has no provenance block; refusing to append.")
    existing = {d["idx"] for d in payload["docs"]}
    new_rows = [r for r in rows if r["idx"] not in existing]
    if len({r["idx"] for r in new_rows}) != len(new_rows):
        raise ValueError("duplicate chunk IDs among injected rows")
    payload["docs"].extend(new_rows)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, path)
    return len(new_rows)
