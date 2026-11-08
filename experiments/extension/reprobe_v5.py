"""Re-run the v5 knowledge probe with disambiguation: gold passage title + subject + relation (no passage text,
no answer). model_knows_o is set from this probe; the first (bare) probe is kept alongside.

Offline parts: rebuild v5's 132 candidates (v4's generated o'), reattach the cached checks and bare probe from
outputs/extension/target_checks_v5/checks_and_probe.json, and keep exactly the 120 swaps and groups already in
data/targets_v5.jsonl. Paid part: one probe call per candidate, own cache. Rewrites data/targets_v5.jsonl and
data/review_v5.md (with a keep column, default y).

    .venv/bin/python experiments/extension/reprobe_v5.py --estimate
    .venv/bin/python experiments/extension/reprobe_v5.py --confirm-paid      # runs only if estimate < --max_inr
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import BASE_OPENIE_STATE, DATASET_DIR, PRICE_USD_PER_M, REPO_ROOT, inr  # noqa: E402
from experiments.extension.select_targets_v5 import (CHECK_CACHE, GENERATIONS_V4, PROBE_MAX_TOKENS, PROBE_SYSTEM,  # noqa: E402
                                                     REVIEW_V5_PATH, TARGETS_V5_PATH, knows, rebuild_v4_candidates,
                                                     review_markdown)

TITLED_PROBE_CACHE = REPO_ROOT / "outputs" / "extension" / "knowledge_probe_v5_titled" / "llm_cache"


def titled_probe_messages(title, s, r):
    user = (f"Complete the fact from memory. Give only the missing object, as a short answer with no explanation.\n"
            f"Topic (Wikipedia article title): {title}\nSubject: {s}\nRelation: {r}\nObject:")
    return [{"role": "system", "content": PROBE_SYSTEM}, {"role": "user", "content": user}]


def merge(candidates, checks_rows, kept_rows):
    """Attach cached checks / bare probe; rename bare-probe fields; carry the kept set's group."""
    by_id = {c["target_id"]: c for c in checks_rows}
    kept_by_id = {k["target_id"]: k for k in kept_rows}
    for t in candidates:
        c = by_id[t["target_id"]]
        if c["o_prime"] != t["o_prime"]:
            raise ValueError(f"{t['target_id']}: o' differs from the v5 checks file")
        t.update(checks=c["checks"], checks_response=c["checks_response"], probe_answer_bare=c["probe_answer"],
                 model_knows_o_bare=c["model_knows_o"], model_knows_o_bare_exact=c["model_knows_o_exact"])
        if t["target_id"] in kept_by_id:
            k = kept_by_id[t["target_id"]]
            if k["swapped_body"] != t["swapped_body"]:
                raise ValueError(f"{t['target_id']}: rebuilt swap differs from targets_v5.jsonl")
            t["group"] = k["group"]
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--max_inr", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    candidates = rebuild_v4_candidates(samples, openie_docs, json.loads(GENERATIONS_V4.read_text(encoding="utf-8")), args.seed)
    checks_rows = json.loads(CHECK_CACHE.parent.joinpath("checks_and_probe.json").read_text(encoding="utf-8"))
    kept_rows = [json.loads(l) for l in TARGETS_V5_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    merge(candidates, checks_rows, kept_rows)

    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    msgs = [titled_probe_messages(t["title"], t["s"], t["r"]) for t in candidates]
    tin = sum(sum(len(enc.encode(m["content"])) + 4 for m in ms) + 3 for ms in msgs)
    usd = (tin * PRICE_USD_PER_M["gpt-4o-mini_in"] + len(msgs) * PROBE_MAX_TOKENS * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    print(json.dumps({"probe_calls": len(msgs), "tokens_in": tin, "tokens_out_max": len(msgs) * PROBE_MAX_TOKENS,
                      "estimate_inr_upper": round(inr(usd), 3)}, indent=1))
    if args.estimate:
        print("\nexample prompt:\n" + msgs[0][1]["content"])
        return
    if inr(usd) >= args.max_inr:
        sys.exit(f"estimate Rs {inr(usd):.2f} is not under Rs {args.max_inr}; not running")

    from experiments.extension.common import capture_config
    from src.hipporag.llm.openai_gpt import CacheOpenAI
    llm = CacheOpenAI(cache_dir=str(TITLED_PROBE_CACHE), global_config=capture_config("/nonexistent/reprobe_v5"))
    usage = collections.Counter()
    for t, m in zip(candidates, msgs):
        text, meta, hit = llm.infer(m, max_new_tokens=PROBE_MAX_TOKENS)
        usage["calls"] += 1
        usage["cache_hits"] += int(bool(hit))
        if not hit:
            usage["prompt_tokens"] += meta.get("prompt_tokens", 0)
            usage["completion_tokens"] += meta.get("completion_tokens", 0)
        t["probe_answer_titled"] = text.strip()
        t["model_knows_o_exact"], t["model_knows_o"] = knows(t["probe_answer_titled"], t["o"], t["answer_aliases"])
        t.pop("probe_answer", None)
    llm.close()

    kept_ids = [k["target_id"] for k in kept_rows]
    by_id = {t["target_id"]: t for t in candidates}
    kept = [by_id[i] for i in kept_ids]
    dropped = [t for t in candidates if t["target_id"] not in set(kept_ids) and not all(t["checks"].values())]
    with open(TARGETS_V5_PATH, "w", encoding="utf-8") as f:
        for t in kept:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    REVIEW_V5_PATH.write_text(review_markdown(kept, dropped), encoding="utf-8")
    TITLED_PROBE_CACHE.parent.joinpath("probe_titled.json").write_text(json.dumps(
        [{k: t[k] for k in ("target_id", "title", "s", "r", "o", "probe_answer_bare", "model_knows_o_bare",
                            "probe_answer_titled", "model_knows_o")} for t in candidates], ensure_ascii=False, indent=1),
        encoding="utf-8")
    usd_actual = (usage["prompt_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_in"]
                  + usage["completion_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    yn = lambda xs: dict(collections.Counter("yes" if x else "no" for x in xs))
    flips = collections.Counter((t["model_knows_o_bare"], t["model_knows_o"]) for t in kept)
    print(json.dumps({
        "usage": dict(usage), "actual_inr": round(inr(usd_actual), 3),
        "kept": len(kept), "model_knows_o_kept (titled)": yn(t["model_knows_o"] for t in kept),
        "model_knows_o_exact_kept (titled)": yn(t["model_knows_o_exact"] for t in kept),
        "model_knows_o_kept (bare, before)": yn(t["model_knows_o_bare"] for t in kept),
        "bare -> titled (kept)": {f"{'yes' if a else 'no'}->{'yes' if b else 'no'}": n for (a, b), n in sorted(flips.items())},
        "model_knows_o_all_132 (titled)": yn(t["model_knows_o"] for t in candidates)}, indent=1))
    print(f"rewrote {TARGETS_V5_PATH} and {REVIEW_V5_PATH}")


if __name__ == "__main__":
    main()
