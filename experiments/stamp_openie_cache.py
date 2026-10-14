"""Make the shipped MuSiQue gpt-4o-mini OpenIE results loadable by HippoRAG 2.0.0a5 without touching src/.

The shipped outputs/musique/openie_results_ner_gpt-4o-mini.json has no "provenance" block, so
HippoRAG.__init__ rejects it (StateConsistencyError). This writes a copy with the provenance the
current code expects to <save_dir>/gpt-4o-mini_<embedding>/openie_state.json, which is read before
the shipped file. The shipped file is left untouched. Offline: HippoRAG is constructed only to read
its expected provenance; no API request is made.

Run from the repo root (imports via `src.hipporag` exactly like main.py, because the provenance
records class module paths):
    python experiments/stamp_openie_cache.py [save_dir] [embedding_name]
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ.setdefault("OPENAI_API_KEY", "sk-offline-placeholder")  # SDK client init only
from src.hipporag.HippoRAG import HippoRAG
from src.hipporag.utils.config_utils import BaseConfig

save_dir = sys.argv[1] if len(sys.argv) > 1 else "outputs/musique"
embedding = sys.argv[2] if len(sys.argv) > 2 else "text-embedding-3-small"
shipped = "outputs/musique/openie_results_ner_gpt-4o-mini.json"
dst = os.path.join(save_dir, f"gpt-4o-mini_{embedding.replace('/', '_')}", "openie_state.json")
if os.path.exists(dst):
    sys.exit(f"{dst} already exists; not overwriting.")

# Same fields main.py sets that feed into the provenance check.
config = dict(llm_base_url="https://api.openai.com/v1", llm_name="gpt-4o-mini", dataset="musique",
              embedding_model_name=embedding,
              rerank_dspy_file_path="src/hipporag/prompts/dspy_prompts/filter_llama3.3-70B-Instruct.json")
with HippoRAG(global_config=BaseConfig(save_dir=tempfile.mkdtemp(), **config)) as probe:
    provenance = probe._current_openie_provenance()

with open(shipped, encoding="utf-8") as f:
    payload = json.load(f)
payload["provenance"] = provenance
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
print(f"Wrote {dst} ({len(payload['docs'])} docs)")
