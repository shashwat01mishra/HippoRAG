"""Shared paths, launch arguments, config capture and string helpers for the extension.

Imports go through `src.hipporag` (as main.py and run_subset.py do), because OpenIE provenance and the
index manifest record class module paths; `hipporag.*` classes would not match the base index.
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.hipporag.utils.misc_utils import text_processing  # noqa: E402  (the graph's entity normalizer)

DATASET_DIR = REPO_ROOT / "reproduce" / "dataset"
EXT_DIR = REPO_ROOT / "experiments" / "extension"
DATA_DIR = EXT_DIR / "data"
TARGETS_PATH = DATA_DIR / "targets.jsonl"

# Base index: the n=100 HippoRAG save dir (the n=500 dir is a copy of it). Read-only for the extension.
BASE_SAVE_DIR = REPO_ROOT / "outputs" / "hipporag_n100_musique"
WORKING_DIR_NAME = "gpt-4o-mini_text-embedding-3-small"
BASE_WORKING_DIR = BASE_SAVE_DIR / WORKING_DIR_NAME
BASE_OPENIE_STATE = BASE_WORKING_DIR / "openie_state.json"

# Exactly the arguments the base HippoRAG index was built with (logs/hipporag_n500_*.log), minus
# --save_dir / --num_queries, which are per run.
LAUNCH_ARGS = [
    "--rag_type", "hipporag", "--dataset", "musique",
    "--llm_base_url", "https://api.aicredits.in/v1", "--llm_name", "gpt-4o-mini",
    "--embedding_name", "text-embedding-3-small", "--embedding_base_url", "https://api.aicredits.in/v1",
    "--embedding_batch_size", "128",
]

# Pricing (list, USD per 1M tokens) and conversion used for every estimate in this extension.
PRICE_USD_PER_M = {"gpt-4o-mini_in": 0.15, "gpt-4o-mini_out": 0.60, "text-embedding-3-small": 0.02}
INR_PER_USD = 88.0
GATEWAY_MULTIPLIER = 1.1


def inr(usd: float) -> float:
    return usd * INR_PER_USD * GATEWAY_MULTIPLIER


def launch_args(save_prefix: str) -> list:
    """Full run_subset.py argument list for a cell. run_subset appends _musique to save_prefix."""
    return LAUNCH_ARGS + ["--save_dir", str(save_prefix), "--num_queries", "1"]


def capture_config(save_prefix: str):
    """BaseConfig exactly as experiments/run_subset.py builds it for these launch args.

    Same capture trick as experiments/verify_openie_cache.py: the RAG classes are stubbed, so nothing
    is constructed or called. Using run_subset's own code means the cell config cannot drift from the
    config the base index was built with.
    """
    spec = importlib.util.spec_from_file_location("_run_subset_capture", REPO_ROOT / "experiments" / "run_subset.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    class _Captured(Exception):
        pass

    class _Stub:
        def __init__(self, global_config):
            captured["config"] = global_config
            raise _Captured

    module.HippoRAG = module.StandardRAG = _Stub
    saved_argv = sys.argv
    sys.argv = ["run_subset.py"] + launch_args(save_prefix)
    try:
        module.main()
    except _Captured:
        pass
    finally:
        sys.argv = saved_argv
    return captured["config"]


def word_pattern(phrase: str, flags=0) -> re.Pattern:
    """Match `phrase` verbatim, not inside a longer alphanumeric token."""
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(phrase) + r"(?![0-9A-Za-z])", flags)


def contains_phrase(text: str, phrase: str, ignore_case: bool = False) -> bool:
    return bool(word_pattern(phrase, re.IGNORECASE if ignore_case else 0).search(text))


def chunk_text(title: str, body: str) -> str:
    """Passage string as main.py / run_subset.py build it (and so as it is hashed into a chunk ID)."""
    return f"{title}\n{body}"
