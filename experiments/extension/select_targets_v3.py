"""Targets v3: every v2 pick, filtered for plausibility and doubled tokens, partitioned into collision-free groups.

Inputs (no picker re-run): the v2 picks (outputs/extension/target_selection_v2/picks.json) and the same seeded
offline preparation as v2 (select_targets_v2.prepare), which rebuilds each picked target deterministically.

Steps
  1. Rebuild all picked targets (no stratum caps, no collision rule yet).
  2. Doubled-token check (offline): at each o -> o' replacement, the word just before o' must not equal o''s
     first word, and the word just after must not equal o''s last word (case-insensitive), e.g. "emperor Emperor
     Wencheng". Hits are dropped, not edited, so old and new passages differ only in o -> o'.
  3. Plausibility (paid, one gpt-4o-mini call per target, own cache namespace): the swapped sentence alone is rated
     1-5 for "would an informed reader find this believable even if it is wrong"; keep 4-5.
  4. Groups: greedy colouring. Targets conflict when they share a normalized s/o/o' entity or the gold passage
     (the v1/v2 collision rule). Within a group the rule holds strictly; each group gets its own index per cell.
  5. Write data/targets_v3.jsonl and data/review_v3.md (common first, then lowest score first).

    .venv/bin/python experiments/extension/select_targets_v3.py --estimate
    .venv/bin/python experiments/extension/select_targets_v3.py --confirm-paid     # runs only if estimate < --max_inr
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import (BASE_OPENIE_STATE, DATA_DIR, DATASET_DIR, PRICE_USD_PER_M, REPO_ROOT,  # noqa: E402
                                          inr, text_processing as tp, word_pattern)
from experiments.extension.select_targets import make_target, sentence_with  # noqa: E402
from experiments.extension.select_targets_v2 import load_entity_vectors, prepare  # noqa: E402

PICKS_V2 = REPO_ROOT / "outputs" / "extension" / "target_selection_v2" / "picks.json"
TARGETS_V3_PATH = DATA_DIR / "targets_v3.jsonl"
REVIEW_V3_PATH = DATA_DIR / "review_v3.md"
DEFAULT_CACHE_DIR = REPO_ROOT / "outputs" / "extension" / "target_plausibility_v3" / "llm_cache"
MAX_OUT_TOKENS = 8
KEEP_MIN_SCORE = 4

SYSTEM = "You judge whether sentences would be believable to an informed reader."


# ------------------------------------------------------------------ 1. rebuild -------------------------
def rebuild_picked(samples, openie_docs, vectors, picks, seed=0):
    """All v2 picks as target records (same fields as v2 targets)."""
    index, prepared, _ = prepare(samples, openie_docs, vectors, seed)
    by_id = {it["entry"][1]["id"]: it for it in prepared}
    all_passages = list(index[0])
    targets = []
    for p in picks:
        if not p.get("o_prime"):
            continue
        item = by_id[p["target_id"]]
        q_index, sample, para, t_index, triple = item["entry"]
        stratum = p["final_stratum"]
        offered = {raw for raw, _, _ in item["pools"][stratum]}
        if p["o_prime"] not in offered:
            raise ValueError(f"{p['target_id']}: pick {p['o_prime']!r} not among the rebuilt {stratum} candidates")
        cos = next(c for raw, _, c in item["pools"][stratum] if raw == p["o_prime"])
        t = make_target(index, all_passages, q_index, sample, para, t_index, triple, p["o_prime"], stratum)
        t.update(o_prime_source="gpt-4o-mini", o_prime_cosine=cos, stratum_changed=p["final_stratum"] != p["assigned_stratum"],
                 assigned_stratum=p["assigned_stratum"])
        targets.append(t)
    return targets


# ------------------------------------------------------------------ 2. doubled tokens ------------------
def doubled_token_hits(body, o, o_prime):
    """Boundary words that duplicate o''s first/last word after the swap (case-insensitive)."""
    hits = []
    swapped = word_pattern(o).sub(lambda _m: "\x00" + o_prime + "\x01", body)
    first, last = o_prime.split()[0].lower(), o_prime.split()[-1].lower()
    for m in re.finditer("\x00([^\x01]*)\x01", swapped):
        before = re.findall(r"[\w'-]+", swapped[:m.start()].replace("\x00", "").replace("\x01", ""))
        after = re.findall(r"[\w'-]+", swapped[m.end():].replace("\x00", "").replace("\x01", ""))
        if before and before[-1].lower() == first:
            hits.append(f"...{before[-1]} {o_prime}")
        if after and after[0].lower() == last:
            hits.append(f"{o_prime} {after[0]}...")
    return hits


# ------------------------------------------------------------------ 3. plausibility --------------------
def plausibility_messages(sentence):
    user = (f"Sentence: {sentence}\n\n"
            "Would an informed reader find this sentence believable, even if it is factually wrong? Rate it from 1 to 5:\n"
            "5 = entirely believable; 4 = believable; 3 = doubtful; 2 = implausible; 1 = obviously impossible.\n"
            "Penalise anachronisms, category errors (the wrong kind of entity in a slot), and the wrong nationality, "
            "region or era.\n\nAnswer with one line: SCORE: <1-5>")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_score(text):
    m = re.search(r"score:\s*([1-5])", text.lower())
    return int(m.group(1)) if m else None


def swapped_sentence(t):
    return sentence_with(t["swapped_body"], t["o_prime"])


# ------------------------------------------------------------------ 4. groups --------------------------
def conflict_keys(t):
    return {("e", tp(t["s"])), ("e", tp(t["o"])), ("e", tp(t["o_prime"])), ("p", t["gold_chunk"])}


def assign_groups(targets):
    """Greedy colouring (Welsh-Powell order: most conflicts first, ties by target_id). Sets t['group']."""
    keys = {t["target_id"]: conflict_keys(t) for t in targets}
    owners = collections.defaultdict(set)
    for tid, ks in keys.items():
        for k in ks:
            owners[k].add(tid)
    degree = {tid: len(set().union(*(owners[k] for k in ks)) - {tid}) for tid, ks in keys.items()}
    group_keys = []                                             # per group: the set of keys used
    for t in sorted(targets, key=lambda t: (-degree[t["target_id"]], t["target_id"])):
        ks = keys[t["target_id"]]
        g = next((i for i, used in enumerate(group_keys) if not (used & ks)), None)
        if g is None:
            group_keys.append(set())
            g = len(group_keys) - 1
        group_keys[g] |= ks
        t["group"] = g
    return len(group_keys)


def check_groups(targets):
    """Raise if any group violates the collision rule."""
    by_group = collections.defaultdict(list)
    for t in targets:
        by_group[t["group"]].append(t)
    for g, ts in by_group.items():
        seen = set()
        for t in ts:
            ks = conflict_keys(t)
            if ks & seen:
                raise AssertionError(f"group {g}: collision at {t['target_id']}")
            seen |= ks


# ------------------------------------------------------------------ 5. outputs -------------------------
def review_markdown(targets):
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")
    rows = sorted(targets, key=lambda t: (t["stratum"] != "common", t["plausibility"], t["target_id"]))
    lines = ["# Targets v3 review", "",
             f"{len(targets)} targets (common first, then lowest plausibility first). Original vs swapped sentence; "
             "o -> o' in bold.", "",
             "| # | target | stratum | score | group | original | swapped |", "|---|---|---|---|---|---|---|"]
    for i, t in enumerate(rows, 1):
        orig = sentence_with(t["body"], t["o"]).replace(t["o"], f"**{t['o']}**")
        new = swapped_sentence(t).replace(t["o_prime"], f"**{t['o_prime']}**")
        lines.append(f"| {i} | {t['target_id']} | {t['stratum']} | {t['plausibility']} | {t['group']} | {cell(orig)} | {cell(new)} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--picks", default=str(PICKS_V2))
    parser.add_argument("--cache_dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--max_inr", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    picks = json.loads(Path(args.picks).read_text(encoding="utf-8"))
    targets = rebuild_picked(samples, openie_docs, load_entity_vectors(), picks, args.seed)
    for t in targets:
        t["doubled_token_hits"] = doubled_token_hits(t["body"], t["o"], t["o_prime"])

    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    msgs = [plausibility_messages(swapped_sentence(t)) for t in targets]
    tin = sum(sum(len(enc.encode(m["content"])) + 4 for m in ms) + 3 for ms in msgs)
    usd = (tin * PRICE_USD_PER_M["gpt-4o-mini_in"] + len(msgs) * MAX_OUT_TOKENS * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    print(json.dumps({"picked_rebuilt": len(targets), "by_stratum": dict(collections.Counter(t["stratum"] for t in targets)),
                      "doubled_token_hits": [(t["target_id"], t["doubled_token_hits"]) for t in targets if t["doubled_token_hits"]],
                      "plausibility_calls": len(msgs), "tokens_in": tin, "tokens_out_max": len(msgs) * MAX_OUT_TOKENS,
                      "estimate_inr": round(inr(usd), 3)}, indent=1, ensure_ascii=False))
    if args.estimate:
        print("\nexample prompt:\n" + msgs[0][1]["content"])
        return
    if inr(usd) >= args.max_inr:
        sys.exit(f"estimate Rs {inr(usd):.2f} is not under Rs {args.max_inr}; not running")

    from experiments.extension.common import capture_config
    from src.hipporag.llm.openai_gpt import CacheOpenAI
    llm = CacheOpenAI(cache_dir=args.cache_dir, global_config=capture_config("/nonexistent/target_plausibility_v3"))
    usage = collections.Counter()
    for t, m in zip(targets, msgs):
        text, meta, hit = llm.infer(m, max_new_tokens=MAX_OUT_TOKENS)
        t["plausibility"] = parse_score(text)
        t["plausibility_response"] = text
        usage["calls"] += 1
        usage["cache_hits"] += int(bool(hit))
        if not hit:
            usage["prompt_tokens"] += meta.get("prompt_tokens", 0)
            usage["completion_tokens"] += meta.get("completion_tokens", 0)
    llm.close()
    Path(args.cache_dir).parent.joinpath("scores.json").write_text(json.dumps(
        [{k: t[k] for k in ("target_id", "stratum", "o", "o_prime", "plausibility", "plausibility_response", "doubled_token_hits")}
         for t in targets], ensure_ascii=False, indent=1), encoding="utf-8")

    reasons = collections.Counter()
    kept = []
    for t in targets:
        if t["doubled_token_hits"]:
            reasons["doubled token at swap boundary"] += 1
        elif t["plausibility"] is None:
            reasons["unparseable score"] += 1
        elif t["plausibility"] < KEEP_MIN_SCORE:
            reasons[f"plausibility < {KEEP_MIN_SCORE}"] += 1
        else:
            kept.append(t)
    n_groups = assign_groups(kept)
    check_groups(kept)
    with open(TARGETS_V3_PATH, "w", encoding="utf-8") as f:
        for t in sorted(kept, key=lambda t: (t["group"], t["target_id"])):
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    REVIEW_V3_PATH.write_text(review_markdown(kept), encoding="utf-8")
    usd_actual = (usage["prompt_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_in"] + usage["completion_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    print(json.dumps({"usage": dict(usage), "actual_inr": round(inr(usd_actual), 3),
                      "score_hist": dict(sorted(collections.Counter(t["plausibility"] for t in targets).items(), key=str)),
                      "score_hist_by_stratum": {s: dict(sorted(collections.Counter(t["plausibility"] for t in targets if t["stratum"] == s).items(), key=str))
                                                for s in ("rare", "common")},
                      "dropped": dict(reasons), "kept": len(kept),
                      "kept_by_stratum": dict(collections.Counter(t["stratum"] for t in kept)),
                      "groups": n_groups, "group_sizes": dict(sorted(collections.Counter(t["group"] for t in kept).items()))},
                     indent=1))
    print(f"wrote {TARGETS_V3_PATH} and {REVIEW_V3_PATH}")


if __name__ == "__main__":
    main()
