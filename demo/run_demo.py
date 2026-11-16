"""Presentation 2 demo: one MuSiQue question through HippoRAG 2, stage by stage.

Default (offline, instant): replay a saved trace from demo/traces/q<N>.json.
    .venv/bin/python demo/run_demo.py                 # question 193
    .venv/bin/python demo/run_demo.py --q 96 --pause  # Enter between stages
    .venv/bin/python demo/run_demo.py --list

Live (paid, usually < Rs 0.1; LLM calls hit the cloned cache when the prompt is unchanged): rerun retrieval
against the saved index (demo/index/, an APFS clone of outputs/hipporag_n500_musique), optionally with tweaks.
    .venv/bin/python demo/run_demo.py --live --q 193
    .venv/bin/python demo/run_demo.py --live --q 193 --damping 0.85 --passage_weight 0.5
    .venv/bin/python demo/run_demo.py --live --q 193 --save    # (re)write demo/traces/q193.{json,md}

Setup / stats (offline):
    .venv/bin/python demo/run_demo.py --make_index    # clone the n=500 index into demo/index/
    .venv/bin/python demo/run_demo.py --graph_stats   # write demo/graph_stats.md
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_lib as D  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--q", type=int, default=D.DEMO_QUESTIONS[0], help="MuSiQue question index (file order)")
    p.add_argument("--live", action="store_true", help="rerun retrieval against the saved index (paid)")
    p.add_argument("--damping", type=float, help="--live only: PPR damping (default from config: 0.5)")
    p.add_argument("--passage_weight", type=float, help="--live only: passage_node_weight (default 0.05)")
    p.add_argument("--no_reader", action="store_true", help="--live only: skip the reader call")
    p.add_argument("--save", action="store_true", help="--live only: write demo/traces/q<N>.json and .md")
    p.add_argument("--pause", action="store_true", help="wait for Enter between stages")
    p.add_argument("--no_color", action="store_true")
    p.add_argument("--list", action="store_true", help="list saved traces")
    p.add_argument("--make_index", action="store_true")
    p.add_argument("--graph_stats", action="store_true")
    a = p.parse_args()
    if not a.live and (a.damping is not None or a.passage_weight is not None or a.save or a.no_reader):
        p.error("--damping, --passage_weight, --save and --no_reader need --live")
    if a.save and (a.damping is not None or a.passage_weight is not None):
        p.error("--save writes the reference trace; run it without tweaks")
    return a


def compare(base, new):
    """One line per change between a saved trace and a tweaked live run."""
    print("\nvs saved trace (default settings):")
    old = [x["chunk"] for x in base["step5_top5"]]   # chunk ids: several passages can share a title
    for x in new["step5_top5"]:
        was = old.index(x["chunk"]) + 1 if x["chunk"] in old else None
        move = "new" if was is None else ("=" if was == x["rank"] else f"was {was}")
        print(f"  {x['rank']}. {'GOLD' if x['gold'] else '    '} {x['title'][:50]:<50} {move}")
    r0, r1 = base["recall_at_5"]["hipporag"], new["recall_at_5"]["hipporag"]
    print(f"  Recall@5 {r0:.2f} -> {r1:.2f}")


def main():
    a = parse_args()
    color = sys.stdout.isatty() and not a.no_color
    pause = (lambda: input("  ... ")) if a.pause else None

    if a.make_index:
        print(f"cloned to {D.make_index()}")
        return
    if a.graph_stats:
        out = D.DEMO_DIR / "graph_stats.md"
        out.write_text(D.graph_stats_markdown(), encoding="utf-8")
        print(f"wrote {out}")
        return
    saved = sorted(D.TRACES_DIR.glob("q*.json"))
    if a.list:
        for f in saved:
            t = json.loads(f.read_text(encoding="utf-8"))
            print(f"--q {t['index']:<4} {t['question']}")
        return

    trace_path = D.TRACES_DIR / f"q{a.q}.json"
    if not a.live:
        if not trace_path.exists():
            raise SystemExit(f"no saved trace for --q {a.q}; saved: {[f.stem for f in saved]} (or use --live)")
        D.render_terminal(json.loads(trace_path.read_text(encoding="utf-8")), color=color, pause=pause)
        return

    D.load_key()
    t0 = time.time()
    print("loading the index (graph, fact/entity/passage vectors) ...", flush=True)
    rag = D.build_rag()
    meter = D.CallMeter(rag)
    rag.prepare_retrieval_objects()
    print(f"loaded in {time.time() - t0:.0f} s; tracing ...", flush=True)
    try:
        t = D.trace_question(rag, a.q, damping=a.damping, passage_weight=a.passage_weight, run_reader=not a.no_reader)
    finally:
        rag.close()
    t["cost"] = meter.summary()
    D.render_terminal(t, color=color, pause=pause)
    if (a.damping is not None or a.passage_weight is not None) and trace_path.exists():
        compare(json.loads(trace_path.read_text(encoding="utf-8")), t)
    if a.save:
        D.TRACES_DIR.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        trace_path.with_suffix(".md").write_text(D.render_markdown(t), encoding="utf-8")
        print(f"\nwrote {trace_path} and {trace_path.with_suffix('.md')}")


if __name__ == "__main__":
    main()
