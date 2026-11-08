"""Targets v5: v4's generated swaps, re-judged with truth-blind yes/no checks; closed-book knowledge probe.

Why: the v3/v4 plausibility rater scored truth, not believability. It marked down swaps whose true value it knew,
so the kept sample over-represented facts the model does not know, which would hide any effect of the model's
prior at the filter stage (B). v5 replaces the rubric with three yes/no checks that explicitly ignore the true value,
and records whether the model knows o closed-book as a covariate (not a filter).

Pipeline (no regeneration)
  1. Rebuild v4's candidates offline: same anchors, same single-valued filter, same one-question-per-passage seeded
     choice; o' = the candidate v4 chose (outputs/extension/target_generation_v4/generations.json), i.e. the first
     that passed the offline checks. The 132 passages that had one.
  2. Checks (paid, own cache; one call): (a) TYPE o' is the same fine-grained type as o; (b) COHERENT the swapped
     sentence is grammatical and coherent; (c) POSSIBLE no impossibility a reader who does not know the fact would
     spot (region in the wrong country, date outside the entity's era, category error). Keep iff all three are yes.
  3. Probe (paid, own cache; separate call, no context): ask for the object of (s, r, ?). model_knows_o = the
     normalized answer equals normalized o (or an answer alias), or contains it as a whole phrase.
  4. Cap 120, collision-free groups (v3 greedy colouring). Frequency of o and o' logged as before.

    .venv/bin/python experiments/extension/select_targets_v5.py --estimate
    .venv/bin/python experiments/extension/select_targets_v5.py --confirm-paid      # runs only if estimate < --max_inr
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
                                          inr)
from experiments.extension.select_targets import build_corpus_index, make_target, sentence_with  # noqa: E402
from experiments.extension.select_targets_v3 import assign_groups, check_groups, swapped_sentence  # noqa: E402
from experiments.extension.select_targets_v4 import GEN_CACHE, N_CAP, anchors_one_per_passage  # noqa: E402
from src.hipporag.utils.eval_utils import normalize_answer  # noqa: E402

GENERATIONS_V4 = GEN_CACHE.parent / "generations.json"
TARGETS_V5_PATH = DATA_DIR / "targets_v5.jsonl"
REVIEW_V5_PATH = DATA_DIR / "review_v5.md"
CHECK_CACHE = REPO_ROOT / "outputs" / "extension" / "target_checks_v5" / "llm_cache"
PROBE_CACHE = REPO_ROOT / "outputs" / "extension" / "knowledge_probe_v5" / "llm_cache"
CHECK_MAX_TOKENS = 20
PROBE_MAX_TOKENS = 24

CHECK_SYSTEM = "You check counterfactual sentences for a test set. You never judge whether a sentence is true."
PROBE_SYSTEM = "Answer factual questions from memory with a short answer only."


# ------------------------------------------------------------------ rebuild -----------------------------
def rebuild_v4_candidates(samples, openie_docs, generations, seed=0):
    anchors, _ = anchors_one_per_passage(samples, openie_docs, seed)
    by_id = {a[1]["id"]: a for a in anchors}
    index = build_corpus_index(openie_docs)
    all_passages = list(index[0])
    targets = []
    for g in generations:
        if not g.get("o_prime"):
            continue
        q_index, sample, para, t_index, triple = by_id[g["target_id"]]
        if triple[2] != g["o"]:
            raise ValueError(f"{g['target_id']}: rebuilt anchor o={triple[2]!r} differs from v4's {g['o']!r}")
        t = make_target(index, all_passages, q_index, sample, para, t_index, triple, g["o_prime"], None)
        t.pop("stratum")
        t.update(o_prime_source="gpt-4o-mini generated (v4)",
                 o_prime_rank=[c for c, _ in g["checks"]].index(g["o_prime"]) + 1)
        targets.append(t)
    return targets


# ------------------------------------------------------------------ checks ------------------------------
def check_messages(t):
    user = (f"Original entity: \"{t['o']}\"\nReplacement entity: \"{t['o_prime']}\"\n"
            f"Sentence with the replacement: {swapped_sentence(t)}\n\n"
            "Ignore what the true value is. Do not judge whether the sentence is factually correct; it is meant to be "
            "false. Answer three questions:\n"
            "TYPE: Is the replacement the same fine-grained type of entity as the original (for example a full date for "
            "a full date, a county for a county, a person for a person, a record label for a record label)?\n"
            "COHERENT: Is the sentence with the replacement grammatical and coherent?\n"
            "POSSIBLE: Is the sentence free of any impossibility that a reader who does not know the fact would spot "
            "(for example a region placed in the wrong country, a date outside the entity's era, a category error)?\n\n"
            "Answer in exactly three lines:\nTYPE: <yes or no>\nCOHERENT: <yes or no>\nPOSSIBLE: <yes or no>")
    return [{"role": "system", "content": CHECK_SYSTEM}, {"role": "user", "content": user}]


def parse_checks(text):
    """{'type': bool|None, 'coherent': ..., 'possible': ...}"""
    out = {}
    for key in ("type", "coherent", "possible"):
        m = re.search(rf"{key}:\s*(yes|no)", text.lower())
        out[key] = None if not m else m.group(1) == "yes"
    return out


# ------------------------------------------------------------------ probe -------------------------------
def probe_messages(s, r):
    user = (f"Complete the fact from memory. Give only the missing object, as a short answer with no explanation.\n"
            f"Subject: {s}\nRelation: {r}\nObject:")
    return [{"role": "system", "content": PROBE_SYSTEM}, {"role": "user", "content": user}]


def knows(answer, o, aliases=()):
    """(exact, contains): normalized equality with o or an alias; or o / an alias as a whole phrase in the answer."""
    a = normalize_answer(answer)
    golds = [normalize_answer(x) for x in [o, *aliases] if normalize_answer(x)]
    exact = any(a == g for g in golds)
    contains = any(re.search(r"(?<!\S)" + re.escape(g) + r"(?!\S)", a) for g in golds)
    return exact, exact or contains


# ------------------------------------------------------------------ outputs -----------------------------
def review_markdown(kept, dropped):
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")

    def yn(v):
        return "?" if v is None else ("yes" if v else "no")

    def table(rows, title, with_keep):
        keep_h, keep_sep = ("keep | ", "---|") if with_keep else ("", "")
        lines = [f"## {title} ({len(rows)})", "",
                 f"| {keep_h}# | target | TYPE | COHERENT | POSSIBLE | knows o | probe (title) | probe (bare) | freq o | freq o' | "
                 "group | original | swapped |",
                 f"|{keep_sep}---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for i, t in enumerate(rows, 1):
            orig = sentence_with(t["body"], t["o"]).replace(t["o"], f"**{t['o']}**")
            new = swapped_sentence(t).replace(t["o_prime"], f"**{t['o_prime']}**")
            c = t["checks"]
            keep = "y | " if with_keep else ""
            lines.append(f"| {keep}{i} | {t['target_id']} | {yn(c['type'])} | {yn(c['coherent'])} | {yn(c['possible'])} | "
                         f"{yn(t['model_knows_o'])} | {cell(t.get('probe_answer_titled', '-'))} | "
                         f"{cell(t.get('probe_answer_bare', t.get('probe_answer', '-')))} | {t['freq_o_graph']} | "
                         f"{t['freq_oprime_graph']} | {t.get('group', '-')} | {cell(orig)} | {cell(new)} |")
        return lines

    key = lambda t: (t["model_knows_o"], t["target_id"])
    lines = ["# Targets v5 review", "",
             "Kept = TYPE, COHERENT and POSSIBLE all yes (truth-blind checks). knows o = the closed-book probe given the gold "
             "passage title, subject and relation answers o (covariate, not a filter); probe (bare) = the first probe, "
             "subject and relation only. One question per gold passage; n = distinct swaps. o -> o' in bold.", "",
             "**Hand review:** set `keep` to `n` for a bad swap (leave `y` otherwise), then run "
             "`.venv/bin/python experiments/extension/finalize_targets.py`.", ""]
    lines += table(sorted(kept, key=key), "Kept", True) + [""] + table(sorted(dropped, key=key), "Dropped by the checks", False)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--estimate", action="store_true")
    mode.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--max_inr", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    generations = json.loads(GENERATIONS_V4.read_text(encoding="utf-8"))
    targets = rebuild_v4_candidates(samples, openie_docs, generations, args.seed)

    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    ntok = lambda ms: sum(len(enc.encode(m["content"])) + 4 for m in ms) + 3
    cmsgs = [check_messages(t) for t in targets]
    pmsgs = [probe_messages(t["s"], t["r"]) for t in targets]
    tin = sum(map(ntok, cmsgs)) + sum(map(ntok, pmsgs))
    tout = len(targets) * (CHECK_MAX_TOKENS + PROBE_MAX_TOKENS)
    usd = (tin * PRICE_USD_PER_M["gpt-4o-mini_in"] + tout * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    print(json.dumps({"candidates_rebuilt": len(targets), "check_calls": len(cmsgs), "probe_calls": len(pmsgs),
                      "tokens_in": tin, "tokens_out_max": tout, "estimate_inr_upper": round(inr(usd), 3)}, indent=1))
    if args.estimate:
        print("\nexample check prompt:\n" + cmsgs[0][1]["content"] + "\n\nexample probe prompt:\n" + pmsgs[0][1]["content"])
        return
    if inr(usd) >= args.max_inr:
        sys.exit(f"estimate Rs {inr(usd):.2f} is not under Rs {args.max_inr}; not running")

    from experiments.extension.common import capture_config
    from src.hipporag.llm.openai_gpt import CacheOpenAI
    config = capture_config("/nonexistent/target_v5")
    checker = CacheOpenAI(cache_dir=str(CHECK_CACHE), global_config=config)
    prober = CacheOpenAI(cache_dir=str(PROBE_CACHE), global_config=config)
    usage = collections.Counter()

    def call(llm, msgs, max_tokens, kind):
        text, meta, hit = llm.infer(msgs, max_new_tokens=max_tokens)
        usage[f"{kind}_calls"] += 1
        usage[f"{kind}_cache_hits"] += int(bool(hit))
        if not hit:
            usage["prompt_tokens"] += meta.get("prompt_tokens", 0)
            usage["completion_tokens"] += meta.get("completion_tokens", 0)
        return text

    for t, cm, pm in zip(targets, cmsgs, pmsgs):
        t["checks_response"] = call(checker, cm, CHECK_MAX_TOKENS, "check")
        t["checks"] = parse_checks(t["checks_response"])
        t["probe_answer"] = call(prober, pm, PROBE_MAX_TOKENS, "probe").strip()
        t["model_knows_o_exact"], t["model_knows_o"] = knows(t["probe_answer"], t["o"], t["answer_aliases"])
    checker.close()
    prober.close()

    funnel = collections.Counter(candidates=len(targets))
    kept, dropped = [], []
    for t in targets:
        c = t["checks"]
        if None in c.values():
            funnel["unparseable checks"] += 1
            dropped.append(t)
        elif all(c.values()):
            kept.append(t)
        else:
            dropped.append(t)
            for key in ("type", "coherent", "possible"):
                funnel[f"{key} = no"] += int(c[key] is False)
    funnel["all three yes"] = len(kept)
    if len(kept) > N_CAP:
        kept = random.Random(args.seed).sample(kept, N_CAP)
    funnel["after cap"] = len(kept)
    n_groups = assign_groups(kept)
    check_groups(kept)
    with open(TARGETS_V5_PATH, "w", encoding="utf-8") as f:
        for t in sorted(kept, key=lambda t: (t["group"], t["target_id"])):
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    REVIEW_V5_PATH.write_text(review_markdown(kept, dropped), encoding="utf-8")
    CHECK_CACHE.parent.joinpath("checks_and_probe.json").write_text(json.dumps(
        [{k: t[k] for k in ("target_id", "o", "o_prime", "checks", "checks_response", "probe_answer",
                            "model_knows_o_exact", "model_knows_o")} for t in targets], ensure_ascii=False, indent=1),
        encoding="utf-8")

    usd_actual = (usage["prompt_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_in"]
                  + usage["completion_tokens"] * PRICE_USD_PER_M["gpt-4o-mini_out"]) / 1e6
    fb = lambda f: "0" if f == 0 else ("1-9" if f < 10 else ">=10")
    print(json.dumps({
        "funnel": dict(funnel), "kept": len(kept), "groups": n_groups,
        "group_sizes": dict(sorted(collections.Counter(t["group"] for t in kept).items())),
        "model_knows_o_kept": dict(collections.Counter("yes" if t["model_knows_o"] else "no" for t in kept)),
        "model_knows_o_all_candidates": dict(collections.Counter("yes" if t["model_knows_o"] else "no" for t in targets)),
        "model_knows_o_exact_kept": sum(t["model_knows_o_exact"] for t in kept),
        "freq_oprime_bins": dict(collections.Counter(fb(t["freq_oprime_graph"]) for t in kept)),
        "freq_o_bins": dict(collections.Counter(fb(t["freq_o_graph"]) for t in kept)),
        "usage": dict(usage), "actual_inr": round(inr(usd_actual), 3)}, indent=1))
    print(f"wrote {TARGETS_V5_PATH} and {REVIEW_V5_PATH}")


if __name__ == "__main__":
    main()
