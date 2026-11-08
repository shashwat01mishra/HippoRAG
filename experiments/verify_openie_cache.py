"""Pre-launch guard: offline, network-blocked check that a HippoRAG run will make 0 OpenIE calls.

Pass the exact arguments the run will be launched with, after `--`. The script captures the
BaseConfig that experiments/run_subset.py builds from them (its RAG classes are stubbed so nothing
runs), then constructs HippoRAG with that exact config, chunks the corpus as index() does, and calls
load_existing_openie(). That validates the stamp's provenance against the launch config and returns
the chunk keys OpenIE would still process. Exit code 0 only if that number is 0.

Side effect, same as the run's own first step: HippoRAG writes index_manifest.json (and an empty
llm_cache dir) for this config in the save dir.

Run from the repo root:
    python experiments/verify_openie_cache.py -- --rag_type hipporag --save_dir outputs/hipporag_n100 ...
"""
import importlib.util
import json
import os
import socket
import sys


def _blocked(*args, **kwargs):
    raise RuntimeError("network blocked by verify_openie_cache.py")


socket.socket.connect = _blocked
socket.create_connection = _blocked
os.environ["OPENAI_API_KEY"] = "sk-offline-placeholder"  # never the real key
os.environ.pop("OPENAI_BASE_URL", None)                  # launches run with it unset

if "--" not in sys.argv:
    sys.exit(__doc__)
launch_args = sys.argv[sys.argv.index("--") + 1:]
# Optional, before "--": --extra_docs <json list of chunk strings>, checked in addition to the corpus
# (the extension's injected passages).
own_args = sys.argv[1:sys.argv.index("--")]
extra_docs = []
if "--extra_docs" in own_args:
    with open(own_args[own_args.index("--extra_docs") + 1], encoding="utf-8") as f:
        extra_docs = json.load(f)

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
spec = importlib.util.spec_from_file_location("run_subset", os.path.join(repo_root, "experiments", "run_subset.py"))
run_subset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_subset)


class _Captured(Exception):
    pass


captured = {}


class _Stub:
    def __init__(self, global_config):
        captured["config"] = global_config
        raise _Captured


run_subset.HippoRAG = run_subset.StandardRAG = _Stub
sys.argv = ["run_subset.py"] + launch_args
try:
    run_subset.main()
except _Captured:
    pass
config = captured["config"]
if "--rag_type" in launch_args and launch_args[launch_args.index("--rag_type") + 1] != "hipporag":
    sys.exit("Only HippoRAG runs use OpenIE; nothing to verify.")

from src.hipporag.HippoRAG import HippoRAG
from src.hipporag.embedding_store import compute_mdhash_id

with open(os.path.join(repo_root, "reproduce", "dataset", f"{config.dataset}_corpus.json"), encoding="utf-8") as f:
    corpus = json.load(f)
docs = [f"{doc['title']}\n{doc['text']}" for doc in corpus]  # as main.py / run_subset.py
docs += extra_docs

with HippoRAG(global_config=config) as rag:
    print(f"working_dir           = {rag.working_dir}")
    print(f"LLM client base_url   = {rag.llm_model.openai_client.base_url}")
    print(f"embed client base_url = {rag.embedding_model.client.base_url}")
    prefix = rag.chunk_embedding_store.namespace + "-"
    chunks = rag._preprocess_docs(docs)
    keys = {compute_mdhash_id(c.content, prefix=prefix) for c in chunks}
    info, to_process = rag.load_existing_openie(keys)
    print(f"corpus docs           = {len(docs) - len(extra_docs)}")
    print(f"extra docs            = {len(extra_docs)}")
    print(f"chunks                = {len(chunks)} ({len(keys)} unique keys)")
    print(f"cached OpenIE rows    = {len(info)}")
    print(f"chunks needing OpenIE = {len(to_process)}  (0 means no OpenIE API calls)")
    sys.exit(0 if len(to_process) == 0 else 1)
