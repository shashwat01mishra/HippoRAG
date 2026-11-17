"""Precision@5 for the n = 500 reproduction runs (offline, no API calls).

Reads results/musique_n500/{hipporag,dense}_per_query_n500.json and reproduce/dataset/musique.json (first 500).
For each question: hits = gold passages in the top 5; recall@5 = hits / #gold; precision@5 = hits / 5.
So precision@5 = recall@5 x #gold / 5 per question (checked for every question). A perfect retriever puts every
gold passage in the top 5, so its precision@5 is min(#gold, 5) / 5.

    .venv/bin/python experiments/precision_at5.py > results/musique_n500/precision_at5.txt
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results" / "musique_n500"


def main():
    samples = json.loads((ROOT / "reproduce" / "dataset" / "musique.json").read_text(encoding="utf-8"))[:500]
    n_gold = [sum(p["is_supporting"] for p in s["paragraphs"]) for s in samples]
    print("$ .venv/bin/python experiments/precision_at5.py")
    print(f"n = {len(samples)} (first 500 questions of reproduce/dataset/musique.json)")
    print("gold passages per question: " + ", ".join(f"{g} gold: {c} questions" for g, c in sorted(collections.Counter(n_gold).items())))
    perfect = sum(min(g, 5) / 5 for g in n_gold) / len(n_gold)
    print(f"perfect retriever mean precision@5: {100 * perfect:.2f}")
    print(f"{'system':<11}{'Recall@5':>10}{'Precision@5':>13}")
    for arm in ("hipporag", "dense"):
        rows = json.loads((R / f"{arm}_per_query_n500.json").read_text(encoding="utf-8"))
        assert len(rows) == len(samples)
        rec, prec = [], []
        for row, sample, g in zip(rows, samples, n_gold):
            assert row["question"] == sample["question"] and len(set(row["gold_docs"])) == g
            hits = len(set(row["gold_docs"]) & set(row["docs"][:5]))
            rec.append(hits / g)
            prec.append(hits / 5)
            assert abs(prec[-1] - rec[-1] * g / 5) < 1e-12
        name = "HippoRAG 2" if arm == "hipporag" else "dense"
        print(f"{name:<11}{100 * sum(rec) / len(rec):>10.2f}{100 * sum(prec) / len(prec):>13.2f}")
    print("identity precision@5 = recall@5 x #gold / 5 holds for every question")


if __name__ == "__main__":
    main()
