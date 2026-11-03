"""PSX native resize benchmark: Qt, Tkinter and Kivy, Rust/Python Cinnamon.

Place in PSX/benchmarks/native_resize_fps.py.

Examples:
  python benchmarks/native_resize_fps.py --adapters qt kivy tk --counts 12 48 200 --engine rust
  python benchmarks/native_resize_fps.py --adapters qt kivy tk --counts 24 96 --engine both --cycles 50

Values called layout_hz measure completed resize->layout transactions per elapsed
second, NOT frames actually shown by the window compositor. See JSON for timings.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")

WIDTHS = (480, 560, 640, 700, 820, 900, 760, 600, 510)
HEIGHT = 650
BUDGET_MS = 1000 / 60


def pct(values, percent):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


def stats(values):
    return {"mean_ms": statistics.mean(values), "p50_ms": pct(values, 50),
            "p95_ms": pct(values, 95), "p99_ms": pct(values, 99),
            "max_ms": max(values)}


def run_cell(args):
    # These imports must run only in the child process: do not mix Qt/Kivy/Tk event loops.
    from grid_resize_interactive import build_workload, mounted_stats
    from psx.core.reconcile import Reconciler
    from psx.layout.contracts.model import AvailableSize, LayoutConstraints
    from psx.layout.engine.backend import load_layout_engine
    from psx.layout.fallback.engine import PythonLayoutEngine

    engine = PythonLayoutEngine() if args.engine == "python" else load_layout_engine()
    if engine.backend_name != args.engine:
        raise RuntimeError(f"Selected {engine.backend_name}, required {args.engine}; Rust wheel missing?")

    def viewport(width):
        return LayoutConstraints(AvailableSize(width, True), AvailableSize(HEIGHT, True))

    # Track solver time separately from UI/layout-commit cost.
    solver = {"calls": {}, "elapsed_ms": {}}
    for method in ("compute", "compute_grid", "compute_provisional", "compute_incremental"):
        original = getattr(engine, method, None)
        if not callable(original):
            continue

        def wrapper(*a, _original=original, _name=method, **kw):
            started = time.perf_counter_ns()
            try:
                return _original(*a, **kw)
            finally:
                solver["calls"][_name] = solver["calls"].get(_name, 0) + 1
                solver["elapsed_ms"][_name] = solver["elapsed_ms"].get(_name, 0.0) + (time.perf_counter_ns() - started) / 1e6

        setattr(engine, method, wrapper)

    observer = None
    watched = None
    root = None
    tk_tag = None
    clock = None
    if args.adapter == "qt":
        from psx.renderers.qt.pyside import PySide6Renderer
        renderer = PySide6Renderer(argv=["psx-resize-fps"], sfle_constraints=viewport(WIDTHS[0]), engine=engine)
    elif args.adapter == "tk":
        from psx.renderers.tkinter.tkinter import TkinterRenderer
        renderer = TkinterRenderer(sfle_constraints=viewport(WIDTHS[0]), engine=engine)
    else:
        from kivy.config import Config
        Config.set("graphics", "width", str(WIDTHS[0]))
        Config.set("graphics", "height", str(HEIGHT))
        from kivy.clock import Clock
        from kivy.core.window import Window
        from psx.renderers.kivy.kivy import KivyRenderer
        clock = Clock
        renderer = KivyRenderer(sfle_constraints=viewport(WIDTHS[0]), engine=engine)

    reconciler = Reconciler(renderer)
    early_patch = None
    early_stage_patch = None
    viewport_patch = None
    commits = []
    events = []
    try:
        # Benchmark-only switches for a valid same-run A/B control.
        if args.disable_early_geometry_reuse:
            from unittest.mock import patch
            from psx.layout.grid.grid_geometry_reuse import AcceptedGridGeometryReuse
            early_patch = patch.object(
                AcceptedGridGeometryReuse, "lookup", return_value=None
            )
            early_patch.start()
            early_stage_patch = patch.object(
                AcceptedGridGeometryReuse, "stage", return_value=None
            )
            early_stage_patch.start()
        if args.disable_viewport_defer:
            from unittest.mock import patch
            from psx.layout.adapters.grid_viewport_workset import GridViewportWorkset
            viewport_patch = patch.object(
                GridViewportWorkset, "plan", return_value=frozenset(),
            )
            viewport_patch.start()
        mounted = reconciler.render(build_workload(args.count, args.scenario, styled=args.scenario == "cards"))
        mounted_nodes, native_widgets = mounted_stats(mounted)
        original_commit = renderer.commit_layout

        def on_commit(instance):
            start = time.perf_counter_ns()
            try:
                return original_commit(instance)
            finally:
                commits.append((renderer._sfle_constraints.width.value, start, time.perf_counter_ns()))

        renderer.commit_layout = on_commit

        if args.adapter == "qt":
            watched = renderer._sfle_watched_widget
            if watched is None:
                raise RuntimeError("Qt resize watcher unavailable")
            core = renderer._qtcore
            qevent = getattr(core.QEvent, "Type", core.QEvent)

            class Observer(core.QObject):
                def eventFilter(self, target, event):
                    if target is watched and event.type() == qevent.Resize:
                        events.append((event.size().width(), time.perf_counter_ns()))
                    return False

            observer = Observer()
            watched.installEventFilter(observer)
            watched.show()

            def resize(width):
                watched.resize(width, HEIGHT)

            def pump():
                renderer.application.processEvents()

            def settled():
                return not renderer._sfle_resize_scheduled and renderer._sfle_resize_pending is None

        elif args.adapter == "tk":
            watched = renderer.root
            tk_tag = f"ResizeBenchmark_{id(watched)}"
            watched.bindtags((tk_tag, *watched.bindtags()))
            watched.bind_class(tk_tag, "<Configure>", lambda e: events.append((e.width, time.perf_counter_ns())))
            watched.deiconify()

            def resize(width):
                watched.geometry(f"{width}x{HEIGHT}")

            def pump():
                watched.update()

            def settled():
                return renderer._sfle_resize_after_id is None and renderer._sfle_resize_pending is None

        else:
            from kivy.core.window import Window
            watched = renderer._sfle_watched_widget
            if watched is None:
                raise RuntimeError("Kivy resize watcher unavailable")
            Window.add_widget(watched)

            def on_size(_widget, size):
                events.append((round(size[0]), time.perf_counter_ns()))

            watched.bind(size=on_size)

            def resize(width):
                # Benchmark the attached root without starting a competing
                # SDL/Cocoa Window resize epoch on macOS Retina.
                watched.size = (width, HEIGHT)

            def pump():
                clock.tick()

            def settled():
                return (renderer._sfle_resize_event is None
                        and renderer._sfle_resize_pending is None
                        and renderer._sfle_window_resize_event is None)

        pump()
        samples = []
        for index in range(args.warmup + args.cycles):
            target = WIDTHS[(index + 1) % len(WIDTHS)]
            prev_events, prev_commits = len(events), len(commits)
            solver_before = dict(solver["elapsed_ms"])
            calls_before = dict(solver["calls"])
            native_counters = {
                name: getattr(engine, name, 0) for name in (
                    "_native_compute_calls", "_native_incremental_calls", "_exact_hits"
                )
            }
            solved_cache = getattr(
                getattr(renderer, "_psx_grid_flow_blueprints", None), "solved", None
            )
            solved_before = getattr(solved_cache, "hits", 0)
            requested = time.perf_counter_ns()
            resize(target)
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                pump()
                if (len(commits) > prev_commits and settled()
                        and renderer._sfle_constraints.width.value == target):
                    break
                time.sleep(0.001)
            else:
                if args.adapter == "kivy":
                    raise RuntimeError(
                        f"kivy: resize to {target}px not committed in {args.timeout}s; "
                        f"root_size={tuple(watched.size)!r}, "
                        f"window_size={tuple(Window.size)!r}, "
                        f"constraint_width={renderer._sfle_constraints.width.value!r}, "
                        f"new_events={events[prev_events:]!r}, "
                        f"new_commits={commits[prev_commits:]!r}, "
                        f"pending={renderer._sfle_resize_pending!r}, "
                        f"root_clock={renderer._sfle_resize_event!r}, "
                        f"window_clock={renderer._sfle_window_resize_event!r}, "
                        f"resize_error={renderer._sfle_resize_error!r}"
                    )
                raise RuntimeError(f"{args.adapter}: resize to {target}px not committed in {args.timeout}s")
            failure = getattr(renderer, "_sfle_resize_error", None)
            if failure is not None:
                raise RuntimeError(f"{args.adapter}: native resize error") from failure
            primary_completed = time.perf_counter_ns()
            matches = [t for w, t in events[prev_events:] if w == target]
            primary_commits = [c for c in commits[prev_commits:] if c[0] == target]
            if not matches or not primary_commits:
                raise RuntimeError(f"Missing native event/commit for {target}px")
            event_at = matches[0]
            last_commit = primary_commits[-1]
            # The primary commit deliberately leaves proven P2 offscreen.
            # Observe and drain the 125ms idle reconciliation as a *separate*
            # metric; otherwise the next resize's samples can absorb stale
            # deferred callbacks from the previous cycle and the A/B falsely
            # credits work that was merely postponed.
            primary_solver_ms = sum(
                solver["elapsed_ms"].get(k, 0) - v
                for k, v in solver_before.items()
            ) + sum(
                v for k, v in solver["elapsed_ms"].items()
                if k not in solver_before
            )
            primary_solver_calls = sum(
                solver["calls"].get(k, 0) - v
                for k, v in calls_before.items()
            ) + sum(
                v for k, v in solver["calls"].items()
                if k not in calls_before
            )
            primary_commit_ms = sum(
                (end - start) / 1e6 for _, start, end in primary_commits
            )
            while time.monotonic() < deadline:
                coordinator = getattr(renderer, "_psx_resize_priority", None)
                if coordinator is None or (
                    not coordinator.active and not coordinator.settling
                ):
                    break
                pump()
                failure = getattr(renderer, "_psx_resize_settle_error", None)
                if failure is not None:
                    raise RuntimeError(
                        f"{args.adapter}: deferred P2 reconciliation failed"
                    ) from failure
                time.sleep(0.001)
            else:
                raise RuntimeError(
                    f"{args.adapter}: P2 work did not settle within "
                    f"{args.timeout}s at width {target}; "
                    f"coordinator={getattr(renderer, '_psx_resize_priority', None)!r}"
                )
            full_completed = time.perf_counter_ns()
            all_commits = [c for c in commits[prev_commits:] if c[0] == target]
            full_commit_ms = sum(
                (end - start) / 1e6 for _, start, end in all_commits
            )
            full_solver_ms = sum(
                solver["elapsed_ms"].get(k, 0) - v
                for k, v in solver_before.items()
            ) + sum(
                v for k, v in solver["elapsed_ms"].items()
                if k not in solver_before
            )
            full_solver_calls = sum(
                solver["calls"].get(k, 0) - v
                for k, v in calls_before.items()
            ) + sum(
                v for k, v in solver["calls"].items()
                if k not in calls_before
            )
            if index >= args.warmup:
                samples.append({
                    "width": target,
                    "event_to_commit_ms": (last_commit[2] - event_at) / 1e6,
                    "request_to_settled_ms": (primary_completed - requested) / 1e6,
                    "request_to_full_settlement_ms": (full_completed - requested) / 1e6,
                    "deferred_reconciliation_ms": (full_completed - primary_completed) / 1e6,
                    "commit_ms": primary_commit_ms,
                    "full_commit_ms": full_commit_ms,
                    "solver_ms": primary_solver_ms,
                    "full_solver_ms": full_solver_ms,
                    "solver_calls": primary_solver_calls,
                    "full_solver_calls": full_solver_calls,
                    "native_rust_compute_calls": getattr(engine, "_native_compute_calls", 0) - native_counters["_native_compute_calls"],
                    "native_rust_incremental_calls": getattr(engine, "_native_incremental_calls", 0) - native_counters["_native_incremental_calls"],
                    "rust_exact_cache_hits": getattr(engine, "_exact_hits", 0) - native_counters["_exact_hits"],
                    "deferred_text_subtree_hits": getattr(
                        getattr(getattr(renderer, "_psx_grid_flow_blueprints", None), "solved", None),
                        "hits", 0,
                    ) - solved_before,
                    "commits": len(primary_commits),
                    "full_commits": len(all_commits),
                    "idle_reconciliation_commits": len(all_commits) - len(primary_commits),
                })
        latencies = [s["event_to_commit_ms"] for s in samples]
        end_to_end = [s["request_to_settled_ms"] for s in samples]
        full_settlement = [s["request_to_full_settlement_ms"] for s in samples]
        elapsed_sec = sum(end_to_end) / 1000
        return {
            "adapter": args.adapter, "engine": args.engine, "scenario": args.scenario,
            "logical_items": args.count, "mounted_nodes": mounted_nodes,
            "native_widgets": native_widgets, "cycles": args.cycles,
            "disable_early_geometry_reuse": args.disable_early_geometry_reuse,
            "disable_viewport_defer": args.disable_viewport_defer,
            "accepted_grid_geometry_hits": getattr(
                getattr(renderer, "_psx_accepted_grid_geometry", None),
                "hits", 0,
            ),
            "accepted_grid_geometry_misses": getattr(
                getattr(renderer, "_psx_accepted_grid_geometry", None),
                "misses", 0,
            ),
            "accepted_grid_batch_hits": getattr(
                getattr(renderer, "_psx_accepted_grid_geometry", None),
                "batch_hits", 0,
            ),
            "early_provisional_p2_groups": getattr(
                getattr(renderer, "_psx_accepted_grid_geometry", None),
                "early_provisional_groups", 0,
            ),
            "warmup": args.warmup, "event_to_commit": stats(latencies),
            "request_to_settled": stats(end_to_end),
            "request_to_full_settlement": stats(full_settlement),
            "deferred_reconciliation": stats(
                [s["deferred_reconciliation_ms"] for s in samples],
            ),
            "solver_total_ms": sum(s["solver_ms"] for s in samples),
            "full_solver_total_ms": sum(s["full_solver_ms"] for s in samples),
            "solver_calls": sum(s["solver_calls"] for s in samples),
            "full_solver_calls": sum(s["full_solver_calls"] for s in samples),
            "native_rust_compute_calls": sum(s["native_rust_compute_calls"] for s in samples),
            "native_rust_incremental_calls": sum(s["native_rust_incremental_calls"] for s in samples),
            "rust_exact_cache_hits": sum(s["rust_exact_cache_hits"] for s in samples),
            "deferred_text_subtree_hits": sum(s["deferred_text_subtree_hits"] for s in samples),
            "rust_exact_cache_entries": len(getattr(engine, "_exact_results", ())),
            "commit_total_ms": sum(s["commit_ms"] for s in samples),
            "full_commit_total_ms": sum(s["full_commit_ms"] for s in samples),
            "idle_reconciliation_commits": sum(
                s["idle_reconciliation_commits"] for s in samples
            ),
            "layout_hz": args.cycles / elapsed_sec if elapsed_sec else None,
            "p95_budget_60hz_pass": pct(latencies,95) <= BUDGET_MS,
            "over_16_67ms_pct": 100*sum(t>BUDGET_MS for t in latencies)/len(latencies),
            "presentation_fps": None,
            "note": (
                "layout_hz measures urgent native resize transaction throughput, "
                "not compositor FPS. request_to_full_settlement includes the "
                "idle P2 reconciliation; the two intervals are reported "
                "separately to distinguish avoided work from postponed work."
            ),
            "samples": samples,
            "environment": {"python": sys.version.split()[0], "system": platform.platform(), "machine": platform.machine()},
        }
    finally:
        if early_patch is not None:
            early_patch.stop()
        if early_stage_patch is not None:
            early_stage_patch.stop()
        if viewport_patch is not None:
            viewport_patch.stop()
        try:
            if args.adapter == "qt" and observer is not None and watched is not None:
                watched.removeEventFilter(observer)
            elif args.adapter == "tk" and watched is not None and tk_tag is not None:
                watched.bindtags(tuple(tag for tag in watched.bindtags() if tag != tk_tag))
            elif args.adapter == "kivy" and watched is not None:
                watched.unbind(size=on_size)
                if watched.parent is Window:
                    Window.remove_widget(watched)
        finally:
            reconciler.unmount()
            if args.adapter == "tk":
                renderer.close()
            elif args.adapter == "qt":
                renderer.application.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapters", nargs="+", choices=("qt", "kivy", "tk"), default=("qt", "kivy", "tk"))
    parser.add_argument("--engine", choices=("rust", "python", "both"), default="rust")
    parser.add_argument("--scenario", choices=("cards", "controls", "flow", "dense-flow", "flex-siblings"), default="cards")
    parser.add_argument("--counts", type=int, nargs="+", default=(12, 48, 100, 250))
    parser.add_argument("--cycles", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=6)
    parser.add_argument("--disable-early-geometry-reuse", action="store_true",
                        help="A/B: remeasure and re-solve whole Grids at every resize")
    parser.add_argument("--disable-viewport-defer", action="store_true",
                        help="A/B: perform complete native widget geometry commits")
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/native-resize-fps"))
    parser.add_argument("--cell", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--adapter", choices=("qt", "kivy", "tk"), help=argparse.SUPPRESS)
    parser.add_argument("--count", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if any(n < 1 for n in args.counts) or args.cycles < 1 or args.warmup < 0 or args.timeout <= 0:
        parser.error("counts and cycles positive, warmup nonnegative, timeout positive")
    if args.cell:
        data = run_cell(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"OK {data['adapter']}/{data['engine']} n={data['logical_items']} p95={data['event_to_commit']['p95_ms']:.2f}ms layout_hz={data['layout_hz']:.1f}")
        return
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    for count in args.counts:
        for adapter in args.adapters:
            for engine in engines:
                target = args.output / f"{args.scenario}-{adapter}-{engine}-{count}.json"
                command = [sys.executable, str(Path(__file__).resolve()),
                           "--cell", "--adapter", adapter, "--engine", engine,
                           "--count", str(count), "--scenario", args.scenario,
                           "--cycles", str(args.cycles), "--warmup", str(args.warmup),
                           "--timeout", str(args.timeout), "--output", str(target)]
                if args.disable_early_geometry_reuse:
                    command.append("--disable-early-geometry-reuse")
                if args.disable_viewport_defer:
                    command.append("--disable-viewport-defer")
                finished = subprocess.run(command, capture_output=True, text=True)
                log = target.with_suffix(".log")
                log.write_text(f"$ {' '.join(command)}\n{finished.stdout}\n{finished.stderr}", encoding="utf-8")
                if finished.returncode:
                    print(f"FAIL {adapter}/{engine} count={count}: {log}", file=sys.stderr)
                    results.append({"adapter":adapter,"engine":engine,"logical_items":count,"error":str(log)})
                else:
                    result = json.loads(target.read_text(encoding="utf-8"))
                    results.append(result)
                    print(f"{adapter:4s} {engine:6s} n={count:5d} widgets={result['native_widgets']:5d} "
                          f"p95={result['event_to_commit']['p95_ms']:8.2f}ms "
                          f"layoutHz={result['layout_hz']:7.1f} "
                          f"60HzBudget={'PASS' if result['p95_budget_60hz_pass'] else 'MISS'}", flush=True)
    (args.output / "summary.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    with (args.output / "summary.csv").open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,fieldnames=("adapter","engine","scenario","logical_items","native_widgets","cycles","p50_ms","p95_ms","p99_ms","layout_hz","p95_budget_60hz_pass","error"))
        writer.writeheader()
        for r in results:
            timing = r.get("event_to_commit",{})
            writer.writerow({k: (timing[k] if k in timing else r.get(k)) for k in writer.fieldnames})
    if any("error" in r for r in results):
        raise SystemExit("At least one cell failed; see .log files and summary.json")

if __name__ == "__main__":
    main()
