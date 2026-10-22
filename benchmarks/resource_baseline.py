"""Reproducible headless resource baseline; intentionally no native toolkit dependencies.

Reports observations, not leak verdicts. Native lifecycle and Kivy long-run
memory investigations are separate scopes.
"""
from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from psx import Flex, Text
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints


def make_renderer():
    return HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )


def process_memory():
    """Return optional process memory metrics; never silently substitute tracemalloc."""
    try:
        import resource
    except ImportError:
        return {"rss_peak_bytes": None, "rss_peak_unit": None, "uss_bytes": None}
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Darwin reports bytes, Linux reports KiB. ru_maxrss is HIGH-WATER, not live RSS.
    factor = 1 if sys.platform == "darwin" else 1024
    return {"rss_peak_bytes": int(raw * factor), "rss_peak_unit": "high_water", "uss_bytes": None}


def view(size, revision=0, reverse=False):
    indices = range(size - 1, -1, -1) if reverse else range(size)
    return Flex(*(Text(f"{i}: {revision if i == 0 else 0}", key=str(i))
                  for i in indices), direction="column")


def sample(*, nodes=16, cycles=100, warmup=10, scenario="mount_unmount"):
    if nodes < 1 or cycles < 1 or warmup < 0:
        raise ValueError("nodes and cycles must be positive and warmup nonnegative")
    supported = ("mount_unmount", "keyed_reorder", "state_like_update", "idle")
    if scenario not in supported:
        raise ValueError(f"Unknown workload {scenario!r}")
    gc.collect()
    tracemalloc.start()
    tree = None
    elapsed = []
    checkpoints = []
    try:
        def one(index):
            nonlocal tree
            if scenario == "mount_unmount":
                tree = Reconciler(make_renderer())
                tree.render(view(nodes, index))
                tree.unmount()
                tree = None
            elif scenario == "idle":
                if tree is None:
                    tree = Reconciler(HeadlessRenderer())
                    tree.render(view(nodes))
            else:
                if tree is None:
                    tree = Reconciler(HeadlessRenderer())
                tree.render(view(nodes, index if scenario == "state_like_update" else 0,
                                 reverse=bool(index % 2) if scenario == "keyed_reorder" else False))

        for i in range(warmup):
            one(i)
        gc.collect()
        before, _ = tracemalloc.get_traced_memory()
        for i in range(cycles):
            start = time.perf_counter_ns()
            one(warmup + i)
            elapsed.append(time.perf_counter_ns() - start)
            if (i + 1) % max(1, cycles // 4) == 0 or i == cycles - 1:
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                checkpoints.append({"cycle": i + 1, "traced_current_bytes": current,
                                    "traced_peak_bytes": peak, "gc_objects": len(gc.get_objects())})
        if tree is not None:
            tree.unmount()
            tree = None
        gc.collect()
        after, peak = tracemalloc.get_traced_memory()
    finally:
        if tree is not None:
            tree.unmount()
        tracemalloc.stop()
    return {"scenario": scenario, "cycles": cycles, "nodes": nodes, "warmup": warmup,
            "mean_ms": round(statistics.mean(elapsed) / 1_000_000, 4),
            "p95_ms": round(sorted(elapsed)[(len(elapsed) * 95 + 99) // 100 - 1] / 1_000_000, 4),
            "traced_before_bytes": before, "traced_after_teardown_bytes": after,
            "traced_retained_delta_bytes": after - before, "traced_peak_bytes": peak,
            "checkpoints": checkpoints, "process_memory": process_memory()}


def run(*, nodes=16, cycles=100, warmup=10):
    return {"schema": 1, "runtime": {"python": sys.version.split()[0],
            "platform": platform.platform(), "implementation": platform.python_implementation()},
            "scope": "headless-only; no native widget counts or native leak certification",
            "measurements": [sample(nodes=nodes, cycles=cycles, warmup=warmup, scenario=name)
                             for name in ("mount_unmount", "keyed_reorder",
                                          "state_like_update", "idle")]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="PSX headless resource baseline")
    parser.add_argument("--nodes", type=int, default=16)
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run(nodes=args.nodes, cycles=args.cycles, warmup=args.warmup)
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
