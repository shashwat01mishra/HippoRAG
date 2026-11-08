"""Offline: seed the dense run's chunk store with HippoRAG's passage vectors.
1) StandardRAG with the exact dense launch config writes its own manifest on an empty store.
2) Copy HippoRAG's vdb_chunk.parquet in.
3) Reopen StandardRAG: manifest must validate, 11,656 rows, IDs/texts == corpus docs."""
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import sys

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network blocked"))
os.environ["OPENAI_API_KEY"] = "sk-offline-placeholder"
os.environ.pop("OPENAI_BASE_URL", None)
sys.path.insert(0, os.getcwd())

spec = importlib.util.spec_from_file_location("rs", "experiments/run_subset.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
box = {}


class Stub:
    def __init__(self, global_config):
        box["c"] = global_config
        raise KeyboardInterrupt


rs.HippoRAG = rs.StandardRAG = Stub
GW = "https://api.aicredits.in/v1"
sys.argv = ["run_subset.py", "--dataset", "musique", "--rag_type", "standard", "--num_queries", "100",
            "--llm_base_url", GW, "--llm_name", "gpt-4o-mini", "--embedding_name", "text-embedding-3-small",
            "--embedding_base_url", GW, "--embedding_batch_size", "128", "--save_dir", "outputs/dense_n100"]
try:
    rs.main()
except KeyboardInterrupt:
    pass
cfg = box["c"]
assert cfg.save_dir == "outputs/dense_n100_musique", cfg.save_dir

from src.hipporag.StandardRAG import StandardRAG
from src.hipporag.embedding_store import compute_mdhash_id

src = "outputs/hipporag_n100_musique/gpt-4o-mini_text-embedding-3-small/chunk_embeddings/vdb_chunk.parquet"
with StandardRAG(global_config=cfg) as d:
    assert not d.chunk_embedding_store.get_all_ids(), "dense chunk store is not empty; refusing"
    dst = d.chunk_embedding_store.filename
print("1) dense manifest written for empty store")

os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy2(src, dst)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
print(f"2) copied -> {dst}  sha256 src={sha(src)} dst={sha(dst)}")

corpus = json.load(open("reproduce/dataset/musique_corpus.json"))
docs = [f"{x['title']}\n{x['text']}" for x in corpus]
with StandardRAG(global_config=cfg) as d:
    ids = set(d.chunk_embedding_store.get_all_ids())
    texts = set(d.chunk_embedding_store.get_all_texts())
print(f"3) reopened OK: rows={len(ids)}  ids==corpus ids: {ids == {compute_mdhash_id(t, 'chunk-') for t in docs}}"
      f"  texts==corpus docs: {texts == set(docs)}")
