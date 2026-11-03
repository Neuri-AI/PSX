"""Trace retained Python allocation sites during Kivy native UI churn.

Run from the PSX repository root under Xvfb:
    xvfb-run -a python scripts/p0_kivy_allocation_trace.py --cycles 5000 \
        --json-out artifacts/kivy-allocation-sites.json

This is a diagnostic attribution tool, not a leak detector.
"""
from __future__ import annotations

import argparse
import gc
import json
import time
import tracemalloc
from pathlib import Path

from p0_memory_soak import make_backend, rss_bytes


def trace_allocations(cycles: int, baseline_at: int, limit: int) -> dict:
    if cycles <= baseline_at or baseline_at < 1:
        raise ValueError("Require 1 <= baseline_at < cycles")
    create, release, flush, close = make_backend("kivy")
    baseline = None
    start_rss = rss_bytes()
    start = time.perf_counter()
    tracemalloc.start(15)
    try:
        for index in range(1, cycles + 1):
            instance, widget = create(index)
            release()
            del instance, widget
            if index == baseline_at or index == cycles:
                for _ in range(3):
                    flush()
                    gc.collect()
                if index == baseline_at:
                    baseline = tracemalloc.take_snapshot()
                    baseline_rss = rss_bytes()
                else:
                    final = tracemalloc.take_snapshot()
                    final_rss = rss_bytes()
        assert baseline is not None
        changes = final.compare_to(baseline, "traceback")
        sites = []
        for statistic in changes:
            if statistic.size_diff <= 0:
                continue
            frame = statistic.traceback[0]
            sites.append({
                "file": frame.filename,
                "line": frame.lineno,
                "size_diff_bytes": statistic.size_diff,
                "count_diff": statistic.count_diff,
                "traceback": [
                    {"file": trace.filename, "line": trace.lineno}
                    for trace in statistic.traceback
                ],
            })
        return {
            "backend": "kivy",
            "cycles": cycles,
            "baseline_at": baseline_at,
            "elapsed_seconds": round(time.perf_counter() - start, 3),
            "start_rss_bytes": start_rss,
            "baseline_rss_bytes": baseline_rss,
            "final_rss_bytes": final_rss,
            "rss_delta_after_baseline_bytes": (
                None if baseline_rss is None or final_rss is None
                else final_rss - baseline_rss
            ),
            "positive_allocation_sites": sites[:limit],
            "total_positive_tracked_bytes": sum(
                max(statistic.size_diff, 0) for statistic in changes
            ),
            "total_negative_tracked_bytes": sum(
                min(statistic.size_diff, 0) for statistic in changes
            ),
            "interpretation": (
                "Python tracemalloc traceback deltas after GC, not proof "
                "that a particular site owns a leaked native object."
            ),
        }
    finally:
        tracemalloc.stop()
        close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=5000)
    parser.add_argument("--baseline-at", type=int, default=500)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    result = trace_allocations(args.cycles, args.baseline_at, args.top)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "backend": "kivy",
        "cycles": args.cycles,
        "rss_delta_after_baseline_bytes": result["rss_delta_after_baseline_bytes"],
        "top_sites": result["positive_allocation_sites"][:8],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
