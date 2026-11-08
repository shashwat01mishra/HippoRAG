"""Step 6: long-context reader arm (code only; reader calls are paid).

The reader gets the question's own MuSiQue paragraphs (all of them, the gold passage in its original form)
plus every variant injected for that question in the cell (n-1 old copies, k corrections), rendered with the
same rag_qa_musique template and "Wikipedia Title: ..." passage format that HippoRAG's own QA step uses.

Passage order: a seeded shuffle per (target, cell). DESIGN DECISION: order is a known confound for readers
(recency/primacy); shuffling avoids systematically placing corrections last.

The scorer labels the parsed answer 'o_prime', 'o', 'both' or 'neither' by normalized phrase containment.
"""
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import chunk_text  # noqa: E402
from experiments.extension.inject import cell_variants  # noqa: E402
from src.hipporag.prompts.prompt_template_manager import PromptTemplateManager  # noqa: E402
from src.hipporag.utils.eval_utils import normalize_answer  # noqa: E402

_TEMPLATES = None


def _manager():
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = PromptTemplateManager(role_mapping={"system": "system", "user": "user", "assistant": "assistant"})
    return _TEMPLATES


def reader_passages(sample, target, n, k, seed=0):
    own = [chunk_text(p["title"], p["paragraph_text"]) for p in sample["paragraphs"]]
    injected = [v["content"] for v in cell_variants([target], n, k)]
    passages = own + injected
    random.Random(f"{seed}|{target['target_id']}|{n}|{k}").shuffle(passages)
    return passages


def build_messages(sample, target, n, k, seed=0):
    """Chat messages for one long-context reader call, as HippoRAG.qa renders them."""
    prompt_user = "".join(f"Wikipedia Title: {p}\n\n" for p in reader_passages(sample, target, n, k, seed))
    prompt_user += "Question: " + sample["question"] + "\nThought: "
    return _manager().render(name="rag_qa_musique", prompt_user=prompt_user)


def parse_answer(response: str) -> str:
    """Same parse as HippoRAG.qa: text after 'Answer:' (whole response if absent)."""
    parts = response.split("Answer:")
    return parts[1].strip() if len(parts) > 1 else response


def _contains(answer_norm: str, phrase: str) -> bool:
    p = normalize_answer(phrase)
    return bool(p) and re.search(r"(?<!\S)" + re.escape(p) + r"(?!\S)", answer_norm) is not None


def classify(answer: str, o: str, o_prime: str, o_aliases=()):
    a = normalize_answer(answer)
    has_new = _contains(a, o_prime)
    has_old = any(_contains(a, x) for x in [o, *o_aliases])
    if has_new and has_old:
        return "both"
    return "o_prime" if has_new else ("o" if has_old else "neither")
