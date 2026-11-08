"""Targets v2: same anchors as v1, but o' is chosen by gpt-4o-mini from same-relation candidates.

v1 drew o' at random from objects seen with the same relation, which produced implausible swaps
("part of the FA Cup"). v2 keeps everything else from v1 (anchor rule, surface checks, rare/common strata,
collision rules, the deterministic text/triple swap) and only changes how o' is picked:
  - for each eligible target, up to 8 candidates passing the surface checks: up to 4 rare + up to 4 common,
    topped up from the other stratum when one is short (seeded per target);
  - one gpt-4o-mini call per target (temperature 0, the run's own endpoint), asking for the candidate of the
    same fine-grained type that makes the swapped sentence plausible but false, or "none";
  - the pick decides the stratum. Triples are still copied from the cache with o replaced, never extracted.
LLM responses are cached in their own namespace (--cache_dir), separate from every run's llm_cache.

    .venv/bin/python experiments/extension/select_targets_v2.py --estimate         # offline: token/cost estimate
    .venv/bin/python experiments/extension/select_targets_v2.py --confirm-paid     # paid: ~1 call per target
"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import (BASE_OPENIE_STATE, DATA_DIR, DATASET_DIR, PRICE_USD_PER_M, REPO_ROOT,  # noqa: E402
                                          inr, text_processing as tp)
from experiments.extension.select_targets import find_eligible, make_target, sentence_with  # noqa: E402

TARGETS_V2_PATH = DATA_DIR / "targets_v2.jsonl"
DEFAULT_CACHE_DIR = REPO_ROOT / "outputs" / "extension" / "target_selection_v2" / "llm_cache"
MAX_CANDIDATES = 8
MAX_OUT_TOKENS = 8

SYSTEM = ("You help build a counterfactual test set. You choose replacement entities that keep a sentence "
          "fluent and plausible while making it factually false.")


def candidate_pool(target_id, rare, common, k=MAX_CANDIDATES, seed=0):
    """Up to k (raw o', freq_graph): up to k/2 from each stratum, topped up from the other; order shuffled."""
    rng = random.Random(f"{seed}|{target_id}")
    rare, common = list(rare), list(common)
    rng.shuffle(rare)
    rng.shuffle(common)
    half = k // 2
    take_r = min(len(rare), max(half, k - len(common)))
    take_c = min(len(common), k - take_r)
    pool = rare[:take_r] + common[:take_c]
    rng.shuffle(pool)
    return pool


def build_messages(sentence, s, r, o, candidates):
    lines = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates, start=1))
    user = (f"Sentence: {sentence}\n"
            f"Fact in the sentence: ({s} | {r} | {o})\n\n"
            f"Replace \"{o}\" with one of the candidates below so that the sentence stays grammatical and plausible "
            f"but becomes false. The candidate must be the same fine-grained type as \"{o}\" (for example a year for "
            f"a year, a full date for a full date, a county for a county, a person for a person, a university for a "
            f"university).\n\nCandidates:\n{lines}\n\n"
            f"Reply with only the number of the best candidate, or the word none if no candidate fits.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_pick(response, n_candidates):
    """1-based index -> 0-based, or None for 'none' / unparseable / out of range."""
    text = response.strip().lower()
    m = re.match(r"^\W*(\d+)", text)
    if not m:
        return None
    i = int(m.group(1))
    return i - 1 if 1 <= i <= n_candidates else None


def prompts_for(eligible, seed=0):
    out = []
    for q_index, sample, para, t_index, triple, rare, common in eligible:
        pool = candidate_pool(sample["id"], rare, common, seed=seed)
        s, r, o = triple
        msgs = build_messages(sentence_with(para["paragraph_text"], o), s, r, o, [c for c, _ in pool])
        out.append((pool, msgs))
    return out


def select_v2(samples, openie_docs, infer, n_max=120, seed=0, rare_max=None, common_min=None):
    """infer(messages) -> (text, metadata, cache_hit). Returns (targets, stats, picks)."""
    from experiments.extension.select_targets import COMMON_MIN, RARE_MAX
    rare_max = RARE_MAX if rare_max is None else rare_max
    common_min = COMMON_MIN if common_min is None else common_min
    index, eligible, reasons = find_eligible(samples, openie_docs)
    all_passages = list(index[0])
    picks, usage = [], collections.Counter()
    for (q_index, sample, para, t_index, triple, rare, common), (pool, msgs) in zip(eligible, prompts_for(eligible, seed)):
        text, meta, hit = infer(msgs)
        usage["calls"] += 1
        usage["cache_hits"] += int(bool(hit))
        usage["prompt_tokens"] += int(meta.get("prompt_tokens", 0)) if not hit else 0
        usage["completion_tokens"] += int(meta.get("completion_tokens", 0)) if not hit else 0
        pick = parse_pick(text, len(pool))
        picks.append({"target_id": sample["id"], "candidates": [c for c, _ in pool], "response": text,
                      "pick": None if pick is None else pool[pick][0]})
        if pick is None:
            reasons["LLM picked none"] += 1
            continue
        o_prime, freq = pool[pick]
        stratum = "rare" if freq <= rare_max else ("common" if freq >= common_min else None)
        picks[-1]["stratum"] = stratum
        picks[-1]["entry"] = (q_index, sample, para, t_index, triple, o_prime, stratum)

    rng = random.Random(seed)
    order = [p for p in picks if p.get("entry")]
    rng.shuffle(order)
    targets, used_entities, used_passages = [], set(), set()
    counts = {"rare": 0, "common": 0}
    for p in order:
        if len(targets) >= n_max:
            break
        q_index, sample, para, t_index, triple, o_prime, stratum = p["entry"]
        if counts[stratum] >= n_max // 2:
            reasons["stratum full"] += 1
            continue
        s, r, o = triple
        ents = {tp(s), tp(o), tp(o_prime)}
        gold = para["title"] + "\n" + para["paragraph_text"]
        if ents & used_entities or gold in used_passages:
            reasons["entity/passage collision with an earlier target"] += 1
            continue
        used_entities |= ents
        used_passages.add(gold)
        counts[stratum] += 1
        t = make_target(index, all_passages, q_index, sample, para, t_index, triple, o_prime, stratum)
        t.update(o_prime_source="gpt-4o-mini", o_prime_candidates=p["candidates"], o_prime_response=p["response"])
        targets.append(t)
    for p in picks:
        p.pop("entry", None)
    stats = {"questions": len(samples), "eligible": len(eligible), "selected": len(targets), "by_stratum": counts,
             "rejections": dict(reasons), "usage": dict(usage)}
    return targets, stats, picks


def estimate(eligible, seed=0):
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    prompts = prompts_for(eligible, seed)
    tokens_in = sum(sum(len(enc.encode(m["content"])) + 4 for m in msgs) + 3 for _, msgs in prompts)
    tokens_out = len(prompts) * MAX_OUT_TOKENS                    # upper bound: replies are capped at 8 tokens
    usd = (tokens_in * PRICE_USD_PER_M["gpt-4o-mini_in"] + tokens_out * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    return {"calls": len(prompts), "tokens_in": tokens_in, "tokens_out_max": tokens_out, "usd": usd, "inr": inr(usd),
            "pool_sizes": dict(collections.Counter(len(p) for p, _ in prompts))}, prompts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--n_max", type=int, default=120)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(TARGETS_V2_PATH))
    parser.add_argument("--cache_dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--show", type=int, default=20)
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    if args.estimate:
        _, eligible, _ = find_eligible(samples, openie_docs)
        est, prompts = estimate(eligible, args.seed)
        print(json.dumps(est, indent=1))
        print("\nexample prompt:\n" + prompts[0][1][1]["content"])
        return

    from experiments.extension.common import capture_config
    from src.hipporag.llm.openai_gpt import CacheOpenAI
    config = capture_config("/nonexistent/target_selection_v2")     # endpoint/model/temperature only
    llm = CacheOpenAI(cache_dir=args.cache_dir, global_config=config)
    targets, stats, picks = select_v2(samples, openie_docs, lambda m: llm.infer(m, max_new_tokens=MAX_OUT_TOKENS),
                                      args.n_max, args.seed)
    out = Path(args.out)
    with open(out, "w", encoding="utf-8") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    Path(args.cache_dir).parent.joinpath("picks.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print(f"wrote {len(targets)} targets to {out}")
    for t in random.Random(args.seed + 1).sample(targets, min(args.show, len(targets))):
        print(f"\n[{t['target_id']}] {t['stratum']}  ({t['s']} | {t['r']} | {t['o']} -> {t['o_prime']})  "
              f"freq o={t['freq_o_graph']}  o'={t['freq_oprime_graph']}")
        print(f"  old: {sentence_with(t['body'], t['o'])}")
        print(f"  new: {sentence_with(t['swapped_body'], t['o_prime'])}")


if __name__ == "__main__":
    main()
