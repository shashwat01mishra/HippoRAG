"""Make the shipped MuSiQue gpt-4o-mini OpenIE results loadable by HippoRAG 2.0.0a5 without touching src/.

The shipped outputs/musique/openie_results_ner_gpt-4o-mini.json has no "provenance" block, so
HippoRAG.__init__ rejects it (StateConsistencyError). This writes a copy with the provenance the
current code expects to <save_dir>/<llm_label>_<embedding_label>/openie_state.json (the run's
working dir, as HippoRAG names it), which is read before the shipped file. The shipped file is
left untouched. Offline: HippoRAG is constructed only to read its expected provenance; no API
request is made.

The provenance records llm_name (identity.model_name) and llm_base_url (producer.endpoint), so
both must equal what main.py will be run with, or the stamp is rejected at load time.

Run from the repo root (imports via `src.hipporag` exactly like main.py, because the provenance
records class module paths):
    python experiments/stamp_openie_cache.py --save_dir outputs/hipporag_musique \
        --llm_name gpt-4o-mini --llm_base_url https://api.aicredits.in/v1
Note: --save_dir here is the final directory. main.py appends _<dataset> to a custom --save_dir,
so `main.py --save_dir outputs/hipporag` uses outputs/hipporag_musique.
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ.setdefault("OPENAI_API_KEY", "sk-offline-placeholder")  # SDK client init only
from src.hipporag.HippoRAG import HippoRAG
from src.hipporag.utils.config_utils import BaseConfig

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--save_dir", required=True, help="Final save dir main.py will use (including the _<dataset> suffix)")
parser.add_argument("--llm_name", required=True, help="Exact --llm_name main.py will be run with")
parser.add_argument("--llm_base_url", required=True, help="Exact --llm_base_url main.py will be run with")
parser.add_argument("--embedding_name", default="text-embedding-3-small")
args = parser.parse_args()

shipped = "outputs/musique/openie_results_ner_gpt-4o-mini.json"

# Same fields main.py sets that feed into the provenance check.
config = dict(llm_base_url=args.llm_base_url, llm_name=args.llm_name, dataset="musique",
              embedding_model_name=args.embedding_name,
              rerank_dspy_file_path="src/hipporag/prompts/dspy_prompts/filter_llama3.3-70B-Instruct.json")
with HippoRAG(global_config=BaseConfig(save_dir=tempfile.mkdtemp(), **config)) as probe:
    provenance = probe._current_openie_provenance()
    working_dir_name = os.path.basename(probe.working_dir)

dst = os.path.join(args.save_dir, working_dir_name, "openie_state.json")
if os.path.exists(dst):
    sys.exit(f"{dst} already exists; not overwriting.")

with open(shipped, encoding="utf-8") as f:
    payload = json.load(f)
payload["provenance"] = provenance
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
print(f"Wrote {dst} ({len(payload['docs'])} docs)")
print(f"provenance.identity.model_name = {provenance['identity']['model_name']}")
print(f"provenance.producer.endpoint   = {provenance['producer']['endpoint']}")
