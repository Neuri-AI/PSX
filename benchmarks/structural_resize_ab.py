"""Paired native resize timings: full snapshot rebuild vs immutable reuse.

Both variants use exactly the same Cinnamon solver, native widgets, CSS,
geometry acceptance and event loop. The control only clears the structural
projection cache before each commit. Time comparisons are diagnostics, not
compositor FPS; the order is ABBA to limit warmup drift.

Use:
  xvfb-run -a python benchmarks/structural_resize_ab.py --engine rust
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from grid_resize_interactive import exercise
from native_resize_scaling import WIDTHS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("rust", "python"), default="rust")
    parser.add_argument("--counts", type=int, default=60)
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.counts < 1 or args.cycles < 1:
        parser.error("Count and cycles must be positive")

    results = []
    for adapter in ("qt", "tk"):
        for rebuild in (True, False, False, True):
            row = exercise(
                args.engine, adapter, args.counts, args.cycles, 1,
                WIDTHS, styled=True, scenario="cards",
                rebuild_snapshots=rebuild,
            )
            assert row["native_widgets"] > 0
            assert row["structural_snapshot_builds"] >= 1
            if rebuild:
                assert row["structural_snapshot_hits"] == 0
                assert row["css_projection_hits"] == 0
            else:
                assert row["structural_snapshot_hits"] >= 1
                assert row["css_projection_hits"] >= 1
            results.append(row)
            print(
                f"{adapter}/{args.engine} rebuild={rebuild} "
                f"mean={row['mean_event_to_commit_ms']:.2f} "
                f"p95={row['p95_event_to_commit_ms']:.2f} "
                f"builds={row['structural_snapshot_builds']} "
                f"hits={row['structural_snapshot_hits']}",
                flush=True,
            )
        matched = [r for r in results if r["adapter"] == adapter]
        forced = statistics.mean(
            r["mean_event_to_commit_ms"] for r in matched
            if r["rebuild_snapshots"]
        )
        reused = statistics.mean(
            r["mean_event_to_commit_ms"] for r in matched
            if not r["rebuild_snapshots"]
        )
        print(
            f"{adapter}/{args.engine} A/B: full rebuild {forced:.2f}ms, "
            f"reuse {reused:.2f}ms; relative change "
            f"{(reused / forced - 1) * 100:+.1f}%",
            flush=True,
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({
            "engine": args.engine,
            "caveat": "Native event to geometry commit, not displayed FPS",
            "rows": results,
        }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
