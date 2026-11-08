"""Build data/targets_final.jsonl from the hand marks in data/review_v5.md (offline).

Reads the 'Kept' table of review_v5.md: the keep column must be y or n for every row, and the rows must be
exactly the targets in targets_v5.jsonl. Targets marked y are written, in targets_v5 order, keeping their
collision groups (removing targets cannot create a collision). Prints the final counts per covariate bin and
whether analysis.py would split on each (every bin >= MIN_BIN).

    .venv/bin/python experiments/extension/finalize_targets.py
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.extension.analysis import MIN_BIN, slice_map  # noqa: E402
from experiments.extension.common import DATA_DIR  # noqa: E402
from experiments.extension.select_targets_v3 import check_groups  # noqa: E402
from experiments.extension.select_targets_v5 import REVIEW_V5_PATH, TARGETS_V5_PATH  # noqa: E402

TARGETS_FINAL_PATH = DATA_DIR / "targets_final.jsonl"


def read_marks(review_text):
    """{target_id: 'y'|'n'} from the 'Kept' table (rows start with '| <keep> | <#> | <target_id> |')."""
    marks, in_kept = {}, False
    for line in review_text.splitlines():
        if line.startswith("## "):
            in_kept = line.startswith("## Kept")
            continue
        if not in_kept or not line.startswith("|") or line.startswith("|---") or line.startswith("| keep"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        keep, target_id = cells[0].lower(), cells[2]
        if keep not in ("y", "n"):
            raise ValueError(f"{target_id}: keep must be y or n, got {cells[0]!r}")
        if target_id in marks:
            raise ValueError(f"{target_id}: listed twice")
        marks[target_id] = keep
    return marks


def finalize(targets, marks):
    ids = [t["target_id"] for t in targets]
    missing, extra = set(ids) - set(marks), set(marks) - set(ids)
    if missing or extra:
        raise ValueError(f"review marks do not match targets_v5.jsonl: missing={sorted(missing)} extra={sorted(extra)}")
    final = [t for t in targets if marks[t["target_id"]] == "y"]
    check_groups(final)
    return final


def report(final):
    fb = lambda f: "0 (absent)" if f == 0 else ("1-9" if f < 10 else ">=10")
    _, splits = slice_map({t["target_id"]: t for t in final})
    return {
        "final": len(final),
        "o_prime_freq": dict(sorted(collections.Counter(fb(t["freq_oprime_graph"]) for t in final).items())),
        "model_knows_o": dict(collections.Counter("yes" if t["model_knows_o"] else "no" for t in final)),
        "o_prime_freq x model_knows_o": {f"{a} / knows {b}": n for (a, b), n in sorted(collections.Counter(
            (fb(t["freq_oprime_graph"]), "yes" if t["model_knows_o"] else "no") for t in final).items())},
        "groups": dict(sorted(collections.Counter(t["group"] for t in final).items())),
        f"analysis splits used (every bin >= {MIN_BIN})": {k: v["used"] for k, v in splits.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--review", default=str(REVIEW_V5_PATH))
    parser.add_argument("--targets", default=str(TARGETS_V5_PATH))
    parser.add_argument("--out", default=str(TARGETS_FINAL_PATH))
    args = parser.parse_args()
    targets = [json.loads(l) for l in Path(args.targets).read_text(encoding="utf-8").splitlines() if l.strip()]
    marks = read_marks(Path(args.review).read_text(encoding="utf-8"))
    final = finalize(targets, marks)
    with open(args.out, "w", encoding="utf-8") as f:
        for t in final:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"marked n: {sum(m == 'n' for m in marks.values())}; wrote {len(final)} targets to {args.out}")
    print(json.dumps(report(final), indent=1))


if __name__ == "__main__":
    main()
