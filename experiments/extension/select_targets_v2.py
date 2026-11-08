"""Targets v2: same anchors as v1; o' chosen by gpt-4o-mini from embedding-nearest same-relation candidates.

Kept from v1: anchor rule, surface checks, rare/common strata (by freq_graph), collision rules, and the
deterministic text/triple swap. Triples are copied from the OpenIE cache with o replaced, never extracted.

Changed:
  single-valued relations only:
    offline - drop the target if its subject already has >= 2 distinct objects for that relation in the corpus;
    LLM     - the picker call also answers whether the subject can hold only one value for the relation;
              targets answered "no" are dropped.
  candidates - same-relation objects ranked by cosine similarity to o, using the base index's entity vectors
              (no API call). Excluded: cosine >= MAX_COS (near-duplicates/aliases), substring either way,
              answer aliases (the last two as in v1). The 8 nearest within the target's assigned stratum are offered.
  retry     - if the pick is "none" (and the relation was not judged multi-valued), one retry with the other
              stratum's 8 nearest; the stratum change is logged.
Stratum assignment before picking: a target with candidates in both strata goes to whichever stratum has fewer
assigned so far (seeded order). Final selection: seeded order, <= n_max/2 per stratum, v1 collision rules.
LLM responses are cached in their own namespace (--cache_dir), separate from every run's llm_cache.

    .venv/bin/python experiments/extension/select_targets_v2.py --estimate         # offline
    .venv/bin/python experiments/extension/select_targets_v2.py --confirm-paid     # paid: 1-2 calls per target
"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import (BASE_OPENIE_STATE, BASE_WORKING_DIR, DATA_DIR, DATASET_DIR,  # noqa: E402
                                          PRICE_USD_PER_M, REPO_ROOT, inr, text_processing as tp)
from experiments.extension.select_targets import find_eligible, make_target, sentence_with  # noqa: E402

TARGETS_V2_PATH = DATA_DIR / "targets_v2.jsonl"
DEFAULT_CACHE_DIR = REPO_ROOT / "outputs" / "extension" / "target_selection_v2" / "llm_cache"
MAX_CANDIDATES = 8
MAX_COS = 0.92
MAX_OUT_TOKENS = 16

SYSTEM = ("You help build a counterfactual test set. You choose replacement entities that keep a sentence "
          "fluent and plausible while making it factually false, and you judge whether a relation is single-valued.")


# ------------------------------------------------------------------ offline filters / ranking ---------
def subject_relation_objects(openie_docs):
    """(norm subject, norm relation) -> set of norm objects across the corpus."""
    out = collections.defaultdict(set)
    for doc in openie_docs:
        for t in doc["extracted_triples"]:
            if isinstance(t, (list, tuple)) and len(t) == 3:
                out[(tp(t[0]), tp(t[1]))].add(tp(t[2]))
    return out


def load_entity_vectors(working_dir=BASE_WORKING_DIR):
    """{normalized entity text: unit vector} from the base index's entity store (read-only)."""
    import pandas as pd
    df = pd.read_parquet(Path(working_dir) / "entity_embeddings" / "vdb_entity.parquet", columns=["content", "embedding"])
    return {c: np.asarray(e, dtype=np.float32) for c, e in zip(df["content"], df["embedding"])}


def ranked(o, pool, vectors, k=MAX_CANDIDATES, max_cos=MAX_COS):
    """k nearest (raw o', freq, cosine) to o among pool, excluding cosine >= max_cos and missing vectors."""
    vo = vectors.get(tp(o))
    if vo is None:
        return []
    scored = []
    for raw, freq in pool:
        v = vectors.get(tp(raw))
        if v is None:
            continue
        cos = float(np.dot(vo, v) / (np.linalg.norm(vo) * np.linalg.norm(v)))
        if cos < max_cos:
            scored.append((raw, freq, cos))
    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored[:k]


# ------------------------------------------------------------------ prompt / parse --------------------
def build_messages(sentence, s, r, o, candidates):
    lines = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates, start=1))
    user = (f"Sentence: {sentence}\n"
            f"Fact in the sentence: ({s} | {r} | {o})\n\n"
            f"Task 1. Replace \"{o}\" with one of the candidates below so that the sentence stays grammatical and "
            f"plausible but becomes false. The candidate must be the same fine-grained type as \"{o}\" (for example a "
            f"year for a year, a full date for a full date, a county for a county, a person for a person, a "
            f"university for a university). If no candidate fits, answer none.\n\nCandidates:\n{lines}\n\n"
            f"Task 2. Can \"{s}\" have only one value for the relation \"{r}\" as used in this sentence (so that a "
            f"different value would contradict it rather than add to it)? Answer yes or no.\n\n"
            f"Answer in exactly two lines:\nPICK: <candidate number or none>\nSINGLE: <yes or no>")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_response(response, n_candidates):
    """-> (0-based pick or None, single: True / False / None if unparseable)."""
    text = response.lower()
    m = re.search(r"pick:\s*(\d+|none)", text)
    pick = None
    if m and m.group(1) != "none":
        i = int(m.group(1))
        pick = i - 1 if 1 <= i <= n_candidates else None
    s = re.search(r"single:\s*(yes|no)", text)
    single = None if not s else s.group(1) == "yes"
    return pick, single


# ------------------------------------------------------------------ selection -------------------------
def prepare(samples, openie_docs, vectors, seed=0):
    """Offline part: eligible anchors -> single-valued filter -> ranked pools -> stratum assignment."""
    index, eligible, reasons = find_eligible(samples, openie_docs)
    by_passage, ent_passages, rel_objects = index
    sro = subject_relation_objects(openie_docs)
    prepared, assigned = [], {"rare": 0, "common": 0}
    order = list(eligible)
    random.Random(seed).shuffle(order)
    for q_index, sample, para, t_index, triple, rare, common in order:
        s, r, o = triple
        if len(sro[(tp(s), tp(r))]) >= 2:
            reasons["multi-valued in corpus (subject has >= 2 objects for the relation)"] += 1
            continue
        pools = {"rare": ranked(o, rare, vectors), "common": ranked(o, common, vectors)}
        options = [name for name in ("rare", "common") if pools[name]]
        if not options:
            reasons["no candidate after cosine filter"] += 1
            continue
        stratum = min(options, key=lambda name: (assigned[name], name))
        assigned[stratum] += 1
        prepared.append({"entry": (q_index, sample, para, t_index, triple), "pools": pools, "stratum": stratum})
    return index, prepared, reasons


def messages_for(item, stratum, seed=0):
    q_index, sample, para, t_index, (s, r, o) = item["entry"]
    pool = list(item["pools"][stratum])
    random.Random(f"{seed}|{sample['id']}|{stratum}").shuffle(pool)    # display order independent of rank
    return pool, build_messages(sentence_with(para["paragraph_text"], o), s, r, o, [c[0] for c in pool])


def select_v2(samples, openie_docs, infer, vectors, n_max=120, seed=0):
    """infer(messages) -> (text, metadata, cache_hit). Returns (targets, stats, picks)."""
    index, prepared, reasons = prepare(samples, openie_docs, vectors, seed)
    all_passages = list(index[0])
    usage = collections.Counter()
    picks = []
    for item in prepared:
        sample = item["entry"][1]
        log = {"target_id": sample["id"], "assigned_stratum": item["stratum"], "calls": []}
        picks.append(log)
        strata = [item["stratum"]] + [x for x in ("rare", "common") if x != item["stratum"] and item["pools"][x]]
        chosen = None
        for attempt, stratum in enumerate(strata[:2]):
            pool, msgs = messages_for(item, stratum, seed)
            text, meta, hit = infer(msgs)
            usage["calls"] += 1
            usage["cache_hits"] += int(bool(hit))
            if not hit:
                usage["prompt_tokens"] += int(meta.get("prompt_tokens", 0))
                usage["completion_tokens"] += int(meta.get("completion_tokens", 0))
            pick, single = parse_response(text, len(pool))
            log["calls"].append({"stratum": stratum, "candidates": [[c, f, round(cos, 4)] for c, f, cos in pool],
                                 "response": text, "pick": None if pick is None else pool[pick][0], "single": single})
            if single is not True:
                reasons["LLM: multi-valued or unparseable SINGLE"] += 1
                break
            if pick is not None:
                chosen = (pool[pick], stratum, attempt)
                break
        if chosen is None:
            if log["calls"] and log["calls"][-1]["single"] is True:
                reasons["LLM picked none (after retry if available)"] += 1
            continue
        (o_prime, freq, cos), stratum, attempt = chosen
        log.update(o_prime=o_prime, final_stratum=stratum, stratum_changed=attempt == 1)
        item["chosen"] = (o_prime, stratum, attempt == 1, cos)

    order = [it for it in prepared if it.get("chosen")]
    random.Random(seed).shuffle(order)
    targets, used_entities, used_passages = [], set(), set()
    counts = {"rare": 0, "common": 0}
    for it in order:
        if len(targets) >= n_max:
            break
        q_index, sample, para, t_index, triple = it["entry"]
        o_prime, stratum, changed, cos = it["chosen"]
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
        t.update(o_prime_source="gpt-4o-mini", o_prime_cosine=cos, stratum_changed=changed,
                 assigned_stratum=it["stratum"])
        targets.append(t)
    stats = {"questions": len(samples), "prepared": len(prepared), "picked": len(order), "selected": len(targets),
             "by_stratum": counts, "stratum_changes": sum(t["stratum_changed"] for t in targets),
             "rejections": dict(reasons), "usage": dict(usage)}
    return targets, stats, picks


def estimate(prepared, seed=0):
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")

    def ntok(msgs):
        return sum(len(enc.encode(m["content"])) + 4 for m in msgs) + 3
    first = [ntok(messages_for(it, it["stratum"], seed)[1]) for it in prepared]
    retry = [ntok(messages_for(it, other, seed)[1]) for it in prepared
             for other in ("rare", "common") if other != it["stratum"] and it["pools"][other]]
    price = lambda tin, n: (tin * PRICE_USD_PER_M["gpt-4o-mini_in"] + n * MAX_OUT_TOKENS * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    lo, hi = price(sum(first), len(first)), price(sum(first) + sum(retry), len(first) + len(retry))
    return {"first_calls": len(first), "first_tokens_in": sum(first), "max_retries": len(retry),
            "retry_tokens_in": sum(retry), "inr_no_retries": inr(lo), "inr_all_retries": inr(hi)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--n_max", type=int, default=120)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(TARGETS_V2_PATH))
    parser.add_argument("--cache_dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--max_inr", type=float, default=3.0, help="refuse to run if the all-retries estimate exceeds this")
    parser.add_argument("--show", type=int, default=20)
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    vectors = load_entity_vectors()
    _, prepared, reasons = prepare(samples, openie_docs, vectors, args.seed)
    est = estimate(prepared, args.seed)
    print(json.dumps({"prepared": len(prepared), "assigned": dict(collections.Counter(p["stratum"] for p in prepared)),
                      "offline_rejections": dict(reasons), **est}, indent=1))
    if args.estimate:
        print("\nexample prompt:\n" + messages_for(prepared[0], prepared[0]["stratum"], args.seed)[1][1]["content"])
        return
    if est["inr_all_retries"] > args.max_inr:
        sys.exit(f"estimate Rs {est['inr_all_retries']:.2f} exceeds --max_inr {args.max_inr}; not running")

    from experiments.extension.common import capture_config
    from src.hipporag.llm.openai_gpt import CacheOpenAI
    config = capture_config("/nonexistent/target_selection_v2")     # endpoint/model/temperature only
    llm = CacheOpenAI(cache_dir=args.cache_dir, global_config=config)
    targets, stats, picks = select_v2(samples, openie_docs, lambda m: llm.infer(m, max_new_tokens=MAX_OUT_TOKENS),
                                      vectors, args.n_max, args.seed)
    llm.close()
    with open(args.out, "w", encoding="utf-8") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    Path(args.cache_dir).parent.joinpath("picks.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
    usd = (stats["usage"].get("prompt_tokens", 0) * PRICE_USD_PER_M["gpt-4o-mini_in"]
           + stats["usage"].get("completion_tokens", 0) * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    print(json.dumps(stats, indent=1))
    print(f"actual tokens -> Rs {inr(usd):.3f} (list x 1.1)")
    print(f"wrote {len(targets)} targets to {args.out}")
    for t in random.Random(args.seed + 1).sample(targets, min(args.show, len(targets))):
        print(f"\n[{t['target_id']}] {t['stratum']}{' (changed)' if t['stratum_changed'] else ''}  "
              f"({t['s']} | {t['r']} | {t['o']} -> {t['o_prime']})  cos={t['o_prime_cosine']:.3f}  "
              f"freq o={t['freq_o_graph']} o'={t['freq_oprime_graph']}")
        print(f"  old: {sentence_with(t['body'], t['o'])}")
        print(f"  new: {sentence_with(t['swapped_body'], t['o_prime'])}")


if __name__ == "__main__":
    main()
