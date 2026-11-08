"""Step 1: pick counterfactual targets offline from the MuSiQue sample and the cached OpenIE triples.

A question qualifies when, across all its supporting passages, exactly one cached triple (s, r, o) has an
object o whose normalized form equals the normalized answer (or an answer alias), and both s and o occur
verbatim in that passage's text. A replacement o' is then drawn from objects seen with the same normalized
relation r in other passages (the type proxy), and stratified by how many corpus passages o' occurs in.

Frequency is measured two ways and both are logged:
  freq_graph: passages whose cached triples contain the normalized entity as subject or object. This is
              len(ent_node_to_chunk_ids[entity]) in the built graph, the divisor of the entity's seed weight.
  freq_text:  passages whose text contains the phrase (case-insensitive, word boundaries).
Strata use freq_graph: rare = freq_graph <= RARE_MAX, common = freq_graph >= COMMON_MIN.

Run from the repo root (offline; reads the base index's OpenIE state, writes experiments/extension/data/):
    .venv/bin/python experiments/extension/select_targets.py
"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.common import (BASE_OPENIE_STATE, DATASET_DIR, TARGETS_PATH, chunk_text,  # noqa: E402
                                          contains_phrase, text_processing as tp, word_pattern)

RARE_MAX = 1
COMMON_MIN = 10
MIN_RELATION_POOL = 3     # distinct normalized objects a relation needs before it counts as a type proxy


_ARTICLES = {"a", "an", "the"}


def _has_shape(text: str) -> tuple:
    """Surface shape that o' must share with o: contains a digit, starts upper-case, starts with an article."""
    words = text.split()
    return (any(ch.isdigit() for ch in text), text[:1].isupper(), bool(words) and words[0].lower() in _ARTICLES)


def build_corpus_index(openie_docs):
    """Per-passage triples plus entity -> passages and relation -> objects maps."""
    by_passage = {}
    ent_passages = collections.defaultdict(set)
    rel_objects = collections.defaultdict(dict)      # norm relation -> {norm object: (raw object, set(passages))}
    for doc in openie_docs:
        passage = doc["passage"]
        triples = [t for t in doc["extracted_triples"] if isinstance(t, (list, tuple)) and len(t) == 3]
        by_passage[passage] = {"doc": doc, "triples": triples}
        for s, r, o in triples:
            ent_passages[tp(s)].add(passage)
            ent_passages[tp(o)].add(passage)
            entry = rel_objects[tp(r)].setdefault(tp(o), (o, set()))
            entry[1].add(passage)
    return by_passage, ent_passages, rel_objects


def text_frequency(phrase: str, passages) -> int:
    pattern = word_pattern(phrase, re.IGNORECASE)
    return sum(1 for p in passages if pattern.search(p))


def find_anchor(sample, by_passage):
    """Return (paragraph, triple_index, triple, reason). reason is None when the question qualifies."""
    answers = {tp(a) for a in [sample["answer"]] + list(sample.get("answer_aliases", []))}
    hits = []
    for para in sample["paragraphs"]:
        if not para["is_supporting"]:
            continue
        entry = by_passage.get(chunk_text(para["title"], para["paragraph_text"]))
        if entry is None:
            return None, None, None, "supporting passage missing from OpenIE cache"
        for i, triple in enumerate(entry["triples"]):
            if tp(triple[2]) in answers:
                hits.append((para, i, triple))
    if len(hits) != 1:
        return None, None, None, f"{'no' if not hits else 'several'} answer-object triples"
    para, i, (s, r, o) = hits[0]
    body = para["paragraph_text"]
    if not s.strip() or not o.strip():
        return None, None, None, "empty subject/object"
    if s not in body or o not in body:
        return None, None, None, "s or o not verbatim in passage text"
    if not contains_phrase(body, o):
        return None, None, None, "o only occurs inside a longer token"
    if contains_phrase(para["title"], o, ignore_case=True):
        return None, None, None, "o occurs in the title line"
    if tp(s) == tp(o):
        return None, None, None, "s == o"
    entry = by_passage[chunk_text(para["title"], body)]
    for j, t in enumerate(entry["triples"]):
        for field in (t[0], t[2]):
            if field != o and tp(o) in tp(field) and tp(field) != tp(o):
                return None, None, None, "o is a proper substring of another entity in the passage triples"
    return para, i, (s, r, o), None


def replacement_candidates(sample, para, triple, rel_objects, ent_passages):
    """o' candidates for one anchor: [(raw o', freq_graph)], before stratification."""
    s, r, o = triple
    pool = rel_objects.get(tp(r), {})
    if len(pool) < MIN_RELATION_POOL:
        return []
    answers = {tp(a) for a in [sample["answer"]] + list(sample.get("answer_aliases", []))}
    own_texts = [chunk_text(p["title"], p["paragraph_text"]) for p in sample["paragraphs"]]
    gold = chunk_text(para["title"], para["paragraph_text"])
    out = []
    for norm_obj, (raw_obj, passages) in pool.items():
        if not norm_obj or len(re.sub(r"[^0-9a-z]", "", norm_obj)) < 2:
            continue
        if norm_obj in answers or norm_obj in (tp(o), tp(s)):
            continue
        if passages == {gold}:
            continue                                   # must appear with r elsewhere
        if tp(o) in norm_obj or norm_obj in tp(o):
            continue
        if _has_shape(raw_obj) != _has_shape(o):
            continue                                   # crude shape guard (see _has_shape)
        if any(contains_phrase(t, raw_obj, ignore_case=True) for t in own_texts):
            continue                                   # not in the question's own paragraphs (incl. the gold one)
        out.append((raw_obj, len(ent_passages.get(norm_obj, ()))))
    return out


def swap_passage(para, triples, o, o_prime):
    """Deterministic swap: o -> o' at word boundaries in the body, and in exactly-matching triple fields."""
    body = word_pattern(o).sub(lambda _m: o_prime, para["paragraph_text"])
    swapped = [[o_prime if f == o else f for f in t] for t in triples]
    return body, swapped


def sentence_with(text: str, phrase: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if phrase in sentence:
            return sentence.strip()
    return text[:200]


def select_targets(samples, openie_docs, n_candidates=120, seed=0):
    by_passage, ent_passages, rel_objects = build_corpus_index(openie_docs)
    all_passages = list(by_passage)
    rng = random.Random(seed)
    reasons = collections.Counter()
    eligible = []
    for q_index, sample in enumerate(samples):
        para, t_index, triple, reason = find_anchor(sample, by_passage)
        if reason:
            reasons[reason] += 1
            continue
        cands = replacement_candidates(sample, para, triple, rel_objects, ent_passages)
        rare = sorted(c for c in cands if c[1] <= RARE_MAX)
        common = sorted(c for c in cands if c[1] >= COMMON_MIN)
        if not rare and not common:
            reasons["no o' candidate in either stratum"] += 1
            continue
        eligible.append((q_index, sample, para, t_index, triple, rare, common))

    rng.shuffle(eligible)
    targets, used_entities, used_passages = [], set(), set()
    counts = {"rare": 0, "common": 0}
    for q_index, sample, para, t_index, triple, rare, common in eligible:
        if len(targets) >= n_candidates:
            break
        options = [name for name, pool in (("rare", rare), ("common", common)) if pool]
        stratum = min(options, key=lambda name: (counts[name], name))
        if counts[stratum] >= n_candidates // 2 and len(options) == 1:
            reasons["stratum full"] += 1
            continue
        o_prime, _ = rng.choice(rare if stratum == "rare" else common)
        s, r, o = triple
        ents = {tp(s), tp(o), tp(o_prime)}
        gold = chunk_text(para["title"], para["paragraph_text"])
        if ents & used_entities or gold in used_passages:
            reasons["entity/passage collision with an earlier target"] += 1
            continue
        used_entities |= ents
        used_passages.add(gold)
        counts[stratum] += 1
        entry = by_passage[gold]
        body, swapped = swap_passage(para, entry["triples"], o, o_prime)
        hop = next((i for i, d in enumerate(sample["question_decomposition"]) if d["paragraph_support_idx"] == para["idx"]), None)
        targets.append({
            "target_id": sample["id"], "sample_index": q_index, "question": sample["question"],
            "answer": sample["answer"], "answer_aliases": sample.get("answer_aliases", []),
            "hop": hop, "n_hops": len(sample["question_decomposition"]),
            "para_idx": para["idx"], "title": para["title"], "body": para["paragraph_text"],
            "gold_chunk": gold, "s": s, "r": r, "o": o, "o_prime": o_prime, "triple_index": t_index,
            "stratum": stratum,
            "freq_o_graph": len(ent_passages.get(tp(o), ())), "freq_o_text": text_frequency(o, all_passages),
            "freq_oprime_graph": len(ent_passages.get(tp(o_prime), ())), "freq_oprime_text": text_frequency(o_prime, all_passages),
            "relation_pool": len(rel_objects[tp(r)]),
            "triples": entry["triples"], "entities": entry["doc"]["extracted_entities"],
            "swapped_body": body, "swapped_triples": swapped,
            "swapped_entities": [o_prime if e == o else e for e in entry["doc"]["extracted_entities"]],
        })
    stats = {"questions": len(samples), "eligible": len(eligible), "selected": len(targets),
             "by_stratum": dict(counts), "rejections": dict(reasons)}
    return targets, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n_candidates", type=int, default=120)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(TARGETS_PATH))
    parser.add_argument("--show", type=int, default=10, help="random swaps to print for review")
    args = parser.parse_args()

    samples = json.loads((DATASET_DIR / "musique.json").read_text(encoding="utf-8"))
    openie_docs = json.loads(Path(BASE_OPENIE_STATE).read_text(encoding="utf-8"))["docs"]
    targets, stats = select_targets(samples, openie_docs, args.n_candidates, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(json.dumps(stats, indent=1))
    print(f"wrote {len(targets)} targets to {out}")
    freq = collections.defaultdict(list)
    for t in targets:
        freq[t["stratum"]].append((t["freq_oprime_graph"], t["freq_o_graph"]))
    for name, rows in freq.items():
        print(f"{name}: n={len(rows)}  o' freq_graph range {min(r[0] for r in rows)}-{max(r[0] for r in rows)}  "
              f"o freq_graph median {sorted(r[1] for r in rows)[len(rows) // 2]}")
    for t in random.Random(args.seed + 1).sample(targets, min(args.show, len(targets))):
        print(f"\n[{t['target_id']}] {t['stratum']}  ({t['s']} | {t['r']} | {t['o']} -> {t['o_prime']})  "
              f"freq o={t['freq_o_graph']}/{t['freq_o_text']}  o'={t['freq_oprime_graph']}/{t['freq_oprime_text']}")
        print(f"  Q: {t['question']}  A: {t['answer']}")
        print(f"  old: {sentence_with(t['body'], t['o'])}")
        print(f"  new: {sentence_with(t['swapped_body'], t['o_prime'])}")


if __name__ == "__main__":
    main()
