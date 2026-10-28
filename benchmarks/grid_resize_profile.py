"""Profile mounted native Grid resize with both Cinnamon engines.

Run after installing the repo and a Qt binding:
    QT_QPA_PLATFORM=offscreen python benchmarks/grid_resize_profile.py --engine both

The timings include native widget measurements and geometry commits, not just
the pure Grid mathematics. Rust must be installed for --engine rust/both.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import statistics
import time
import pstats

from psx import Grid, GridItem, Text, Flex
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


def viewport(width):
    return LayoutConstraints(
        AvailableSize(width, True), AvailableSize(650, True)
    )


def cards(count):
    return Grid(
        *(
            GridItem(
                Flex(
                    Text(f"Card {index}", key="title"),
                    Text(f"Value {index * 17}", key="value"),
                    direction="column", gap="8px",
                ),
                key=f"card-{index}",
            )
            for index in range(count)
        ),
        gap="16px",
    )


def measure(engine_name, widths, card_count, warmup, cycles, top, adapter="qt"):
    if engine_name == "python":
        engine = PythonLayoutEngine()
    else:
        engine = load_layout_engine()
    if engine.backend_name != engine_name:
        raise RuntimeError(
            f"Requested Cinnamon {engine_name}, got {engine.backend_name}; "
            "install the Rust extension instead of benchmarking a fallback."
        )
    if adapter == "qt":
        renderer = PySide6Renderer(
            argv=["psx-grid-resize-profile"], sfle_constraints=viewport(widths[0]),
            engine=engine,
        )
    elif adapter == "tk":
        renderer = TkinterRenderer(
            sfle_constraints=viewport(widths[0]), engine=engine,
        )
    else:
        raise ValueError("Unknown native renderer for resize profiling.")
    tree = Reconciler(renderer)
    profiler = cProfile.Profile()
    try:
        root = tree.render(cards(card_count))
        for idx in range(warmup):
            renderer.set_sfle_constraints(viewport(widths[idx % len(widths)]))
            renderer.commit_layout(root)
        times = []
        cpu_times = []
        profiler.enable()
        for idx in range(cycles):
            renderer.set_sfle_constraints(viewport(widths[(idx + 1) % len(widths)]))
            wall = time.perf_counter_ns()
            cpu = time.process_time_ns()
            renderer.commit_layout(root)
            cpu_times.append((time.process_time_ns() - cpu) / 1e6)
            times.append((time.perf_counter_ns() - wall) / 1e6)
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(top)
        return dict(
            engine=engine_name, adapter=adapter, cards=card_count, cycles=cycles, warmup=warmup,
            widths=widths, mean_wall_ms=statistics.mean(times),
            p95_wall_ms=sorted(times)[(len(times) * 95 + 99) // 100 - 1],
            mean_cpu_ms=statistics.mean(cpu_times),
            profile=stream.getvalue(),
        )
    finally:
        profiler.disable()
        tree.unmount()
        if adapter == "qt":
            renderer.application.processEvents()
        else:
            renderer.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--adapter", choices=("qt", "tk", "both"), default="both")
    parser.add_argument("--cards", type=int, default=24)
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    if args.cards < 1 or args.cycles < 1 or args.warmup < 0:
        parser.error("cards and cycles must be positive, warmup nonnegative")
    widths = [680, 760, 800, 900, 1000, 1200, 980, 750]
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    adapters = ("qt", "tk") if args.adapter == "both" else (args.adapter,)
    print(json.dumps(
        [measure(engine, widths, args.cards, args.warmup, args.cycles, args.top, adapter)
         for engine in engines for adapter in adapters], indent=2
    ))


if __name__ == "__main__":
    main()
