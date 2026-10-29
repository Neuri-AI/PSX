"""Native resize scaling probe: logical items, mounted widgets, and frame budgets.

This is NOT a compositor FPS benchmark. A native event-to-layout-commit
duration is necessary but insufficient for stable visual 60 Hz rendering.

Examples:
  QT_QPA_PLATFORM=offscreen xvfb-run -a python benchmarks/native_resize_scaling.py --adapter both --engine rust --counts 6 24 60 120 --scenarios cards controls flow --output scaling.json
  python benchmarks/native_resize_scaling.py --adapter qt --engine rust --counts 6 24 60 --cycles 8
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from grid_resize_interactive import exercise


# Keep all native windows inside the smallest CI display bounds. Windows
# Tk caps to the desktop work area even when geometry() requests more.
# This width sequence still traverses Grid responsive breakpoints.
WIDTHS = (480, 560, 640, 700, 760, 720, 600, 510)
FRAME_BUDGET_MS = 1000 / 60


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=("qt", "tk", "both"), default="both")
    parser.add_argument("--engine", choices=("python", "rust", "both"), default="rust")
    parser.add_argument("--counts", type=int, nargs="+", default=(6, 24, 60, 120))
    parser.add_argument("--scenarios", nargs="+", choices=("cards", "controls", "flow", "dense-flow"),
                        default=("cards", "controls", "flow"))
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if (any(n < 1 for n in args.counts) or len(set(args.counts)) != len(args.counts)
            or args.cycles < 1 or args.warmup < 0):
        parser.error("counts must be distinct and positive; cycles positive and warmup nonnegative")

    adapters = ("qt", "tk") if args.adapter == "both" else (args.adapter,)
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    results = []
    for scenario in args.scenarios:
        for count in sorted(args.counts):
            for adapter in adapters:
                for engine in engines:
                    try:
                        row = exercise(
                            engine, adapter, count, args.cycles, args.warmup, WIDTHS,
                            scenario=scenario, styled=(scenario == "cards"),
                        )
                    except Exception as exc:
                        row = dict(
                            engine=engine, adapter=adapter, logical_items=count,
                            scenario=scenario, error=f"{type(exc).__name__}: {exc}",
                        )
                    else:
                        row["under_60hz_p95"] = row["p95_event_to_commit_ms"] <= FRAME_BUDGET_MS
                        row["under_60hz_all_samples"] = all(
                            item["native_event_to_commit_end_ms"] <= FRAME_BUDGET_MS
                            for item in row["samples"]
                        )
                    results.append(row)
                    if args.output:
                        args.output.parent.mkdir(parents=True, exist_ok=True)
                        args.output.write_text(
                            json.dumps(
                                dict(budget_ms=FRAME_BUDGET_MS, rows=results,
                                     caveat="native event->Cinnamon commit, not displayed FPS"),
                                indent=2,
                            ), encoding="utf-8",
                        )
                    if "error" in row:
                        print(f"{scenario:8} n={count:4} {adapter:2}/{engine:6} ERROR: {row['error']}",
                              file=sys.stderr, flush=True)
                    else:
                        print(
                            f"{scenario:8} n={count:4} {adapter:2}/{engine:6} "
                            f"widgets={row['native_widgets']:4} "
                            f"mean={row['mean_event_to_commit_ms']:8.2f} ms "
                            f"p95={row['p95_event_to_commit_ms']:8.2f} ms "
                            f"p99={row['p99_event_to_commit_ms']:8.2f} ms "
                            f"settle={row['mean_request_to_loop_settled_ms']:8.2f} ms",
                            flush=True,
                        )
    if any("error" in row for row in results):
        raise SystemExit("Scaling benchmark failed: check the partial JSON artifact above.")


if __name__ == "__main__":
    main()
