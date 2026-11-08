"""Paired bootstrap 95% CIs for the HippoRAG 2 - dense gap in Recall@5 and QA F1 (offline, no API calls).

Inputs are the per_query_n<N>.json files written by experiments/run_subset.py. Per-question scores are
recomputed with the repo's own evaluators (RetrievalRecall, QAF1Score, QAExactMatch); the pooled means
are printed so they can be checked against the run logs before the CIs are trusted.

Pairing: question i of one file is matched with question i of the other (both are the first N questions of
reproduce/dataset/<dataset>.json, in order); the script checks that the questions agree. Each resample draws
N question indices with replacement and applies them to both systems, so the CI is for the mean paired
difference. Percentile intervals, fixed seed.

usage: python experiments/bootstrap_gap.py --hipporag <file> --dense <file> [--first N] [--resamples 10000] [--seed 0]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hipporag.evaluation.qa_eval import QAExactMatch, QAF1Score  # noqa: E402
from src.hipporag.evaluation.retrieval_eval import RetrievalRecall  # noqa: E402


def per_question(rows):
    gold_docs = [r["gold_docs"] for r in rows]
    retrieved = [r["docs"] for r in rows]
    gold_answers = [r["gold_answers"] for r in rows]
    answers = [r["answer"] for r in rows]
    _, rec = RetrievalRecall().calculate_metric_scores(gold_docs=gold_docs, retrieved_docs=retrieved, k_list=[5])
    _, f1 = QAF1Score().calculate_metric_scores(gold_answers=gold_answers, predicted_answers=answers, aggregation_fn=np.max)
    _, em = QAExactMatch().calculate_metric_scores(gold_answers=gold_answers, predicted_answers=answers, aggregation_fn=np.max)
    return {"Recall@5": np.array([x["Recall@5"] for x in rec]),
            "F1": np.array([x["F1"] for x in f1]),
            "EM": np.array([x["ExactMatch"] for x in em])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hipporag", required=True)
    p.add_argument("--dense", required=True)
    p.add_argument("--dataset", default="musique")
    p.add_argument("--first", type=int, default=None, help="use only the first N questions of both files")
    p.add_argument("--resamples", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    hip = json.load(open(args.hipporag, encoding="utf-8"))
    den = json.load(open(args.dense, encoding="utf-8"))
    n = args.first or min(len(hip), len(den))
    if n > len(hip) or n > len(den):
        raise SystemExit(f"--first {n} exceeds file lengths {len(hip)}, {len(den)}")
    hip, den = hip[:n], den[:n]

    samples = json.load(open(PROJECT_ROOT / "reproduce" / "dataset" / f"{args.dataset}.json", encoding="utf-8"))[:n]
    for i, (h, d, s) in enumerate(zip(hip, den, samples)):
        if not (h["index"] == d["index"] == i and h["question"] == d["question"] == s["question"]):
            raise SystemExit(f"question mismatch at position {i}")

    H, D = per_question(hip), per_question(den)
    rng = np.random.default_rng(args.seed)
    idx = rng.integers(0, n, size=(args.resamples, n))

    print(f"n = {n} (first {n} questions of {args.dataset}.json), {args.resamples} paired resamples, seed {args.seed}")
    print(f"{'metric':<10}{'HippoRAG 2':>12}{'dense':>10}{'gap':>9}   95% CI (percentile)   P(gap<=0)")
    for m in ("Recall@5", "F1", "EM"):
        diff = H[m] - D[m]
        boots = diff[idx].mean(axis=1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        print(f"{m:<10}{100 * H[m].mean():>12.2f}{100 * D[m].mean():>10.2f}{100 * diff.mean():>+9.2f}"
              f"   [{100 * lo:+6.2f}, {100 * hi:+6.2f}]      {np.mean(boots <= 0):.4f}")
    wins = lambda m: (int((H[m] > D[m]).sum()), int((H[m] < D[m]).sum()), int((H[m] == D[m]).sum()))
    for m in ("Recall@5", "F1"):
        print(f"{m} per question: HippoRAG better {wins(m)[0]}, dense better {wins(m)[1]}, tied {wins(m)[2]}")


if __name__ == "__main__":
    main()
