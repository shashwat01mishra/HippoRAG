"""Step 3: per-cell index = APFS clone of the base save dir + incremental index of only the injected passages.

clone_base   cp -c (clonefile) of every entry in the base save dir except llm_cache, lock files and
             per-query dumps. The base is only read. cp -c fails rather than falling back to a full copy
             when cloning is impossible (e.g. a different volume).
             llm_cache becomes a symlink to one shared cache dir, so a filter prompt repeated across cells
             is paid once.
prepare_cell clone + append the injected OpenIE rows to the clone's openie_state.json (provenance kept).
index_cell   HippoRAG.index on the injected chunks with a FrozenEmbedder installed and OpenIE replaced by
             a sentinel that raises, so a cell can make neither embedding nor OpenIE calls.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.inject import append_openie_rows, as_chunks, openie_rows  # noqa: E402

SKIP_IN_CLONE = {"llm_cache"}


class OpenIECalled(RuntimeError):
    pass


class NoOpenIE:
    """Replaces rag.openie in a cell: any extraction request is a bug (the cache should cover everything)."""

    def batch_openie(self, rows):
        raise OpenIECalled(f"OpenIE was asked to extract {len(rows)} chunk(s); the injected rows should be cached")


def clone_base(base_save_dir, cell_save_dir, shared_cache_dir=None):
    base, cell = Path(base_save_dir), Path(cell_save_dir)
    if cell.exists():
        raise FileExistsError(f"{cell} exists; every cell gets a fresh clone")
    if cell.resolve() == base.resolve():
        raise ValueError("cell dir is the base dir")
    cell.mkdir(parents=True)
    for entry in sorted(base.iterdir()):
        if entry.name in SKIP_IN_CLONE or entry.name.endswith(".lock") or entry.name.startswith("per_query"):
            continue
        subprocess.run(["cp", "-c", "-R", str(entry), str(cell / entry.name)], check=True)
    for lock in cell.rglob("*.lock"):
        lock.unlink()
    if shared_cache_dir is not None:
        Path(shared_cache_dir).mkdir(parents=True, exist_ok=True)
        os.symlink(Path(shared_cache_dir).resolve(), cell / "llm_cache")
    return cell


def prepare_cell(base_save_dir, cell_save_dir, working_dir_name, variants, shared_cache_dir=None):
    cell = clone_base(base_save_dir, cell_save_dir, shared_cache_dir)
    appended = append_openie_rows(cell / working_dir_name / "openie_state.json", openie_rows(variants))
    return cell, appended


def index_cell(rag, variants, embedder):
    """Index the injected chunks; returns call counts. rag must already have embedder installed."""
    rag.openie = NoOpenIE()
    calls_before, served_before = embedder.calls, embedder.texts_served
    if variants:
        rag.index(as_chunks(variants))
    return {"embed_lookups": embedder.calls - calls_before, "vectors_served": embedder.texts_served - served_before,
            "injected_chunks": len(variants)}


def remove_cell(cell_save_dir):
    """Delete a cell clone (only for scratch measurements / tests)."""
    shutil.rmtree(cell_save_dir)
