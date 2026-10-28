"""Measure real native resize-event to Cinnamon commit and event-loop settle.

Unlike grid_resize_profile.py this drives actual Qt Resize/Tk Configure
events. Idle-loop drain is an observable proxy, NOT compositor presentation
or FPS; offscreen/Xvfb cannot provide verified on-screen frame timestamps.

Example:
  QT_QPA_PLATFORM=offscreen xvfb-run -a python benchmarks/grid_resize_interactive.py --adapter both --engine both --cycles 12
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

from grid_resize_profile import cards, viewport
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine


def percentile(values, percentage):
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * percentage + 99) // 100 - 1)]


def exercise(engine_name, adapter, card_count, cycles, warmup, widths):
    engine = PythonLayoutEngine() if engine_name == "python" else load_layout_engine()
    if engine.backend_name != engine_name:
        raise RuntimeError(f"Expected Cinnamon {engine_name}, got {engine.backend_name}")
    if adapter == "qt":
        renderer = PySide6Renderer(
            argv=["psx-grid-interactive-resize"], sfle_constraints=viewport(widths[0]),
            engine=engine,
        )
    else:
        renderer = TkinterRenderer(sfle_constraints=viewport(widths[0]), engine=engine)
    # Native event benchmarking does not log to stdout.
    tree = Reconciler(renderer)
    events = []
    commits = []
    paints = []
    native_observer = None
    try:
        pass  # the first native mount is excluded from timing
        mounted = tree.render(cards(card_count))
        original_commit = renderer.commit_layout

        def timed_commit(root):
            started = time.perf_counter_ns()
            try:
                return original_commit(root)
            finally:
                commits.append((
                    renderer._sfle_constraints.width.value,
                    started, time.perf_counter_ns(),
                ))

        renderer.commit_layout = timed_commit
        if adapter == "qt":
            native = renderer._sfle_watched_widget
            if native is None:
                raise RuntimeError("Qt native viewport observer not installed")
            core = renderer._qtcore
            qevent = getattr(core.QEvent, "Type", core.QEvent)
            resize_type, paint_type = qevent.Resize, qevent.Paint

            class Observer(core.QObject):
                def eventFilter(self, watched, event):
                    if watched is native:
                        if event.type() == resize_type:
                            events.append((event.size().width(), time.perf_counter_ns()))
                        elif event.type() == paint_type:
                            paints.append(time.perf_counter_ns())
                    return False

            native_observer = Observer()
            native.installEventFilter(native_observer)
            native.show()

            def resize(width):
                native.resize(width, 650)

            def pump():
                renderer.application.processEvents()

            def settled():
                return not renderer._sfle_resize_scheduled and renderer._sfle_resize_pending is None

        else:
            native = renderer.root
            native.bind("<Configure>",
                        lambda event: events.append((event.width, time.perf_counter_ns()))
                        if event.widget is native else None, add="+")
            native.bind("<Expose>", lambda event: paints.append(time.perf_counter_ns())
                        if event.widget is native else None, add="+")
            native.deiconify()

            def resize(width):
                native.geometry(f"{width}x650")

            def pump():
                native.update()

            def settled():
                return renderer._sfle_resize_after_id is None and renderer._sfle_resize_pending is None

        pump()
        samples = []
        for index in range(warmup + cycles):
            target = widths[(index + 1) % len(widths)]
            event_count, commit_count, paint_count = len(events), len(commits), len(paints)
            requested_at = time.perf_counter_ns()
            resize(target)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                pump()
                if (len(commits) > commit_count and settled()
                        and renderer._sfle_constraints.width.value == target):
                    break
                time.sleep(0.002)
            else:
                raise RuntimeError(
                    f"Native {adapter} resize {target} did not produce a completed Cinnamon commit"
                )
            finished_at = time.perf_counter_ns()
            observed = [t for w, t in events[event_count:] if w == target]
            matching = [entry for entry in commits[commit_count:] if entry[0] == target]
            if not observed or not matching:
                raise RuntimeError("Missing native resize event or geometry commit timestamp")
            event_at = observed[0]
            commit_started, commit_ended = matching[-1][1:]
            if index >= warmup:
                samples.append({
                    "target_width": target,
                    "request_to_native_event_ms": (event_at - requested_at) / 1e6,
                    "native_event_to_commit_end_ms": (commit_ended - event_at) / 1e6,
                    "commit_wall_ms": (commit_ended - commit_started) / 1e6,
                    "commit_to_loop_settled_ms": (finished_at - commit_ended) / 1e6,
                    "request_to_loop_settled_ms": (finished_at - requested_at) / 1e6,
                    "paint_notifications": len(paints) - paint_count,
                    "commits": len(matching),
                })
        print("samples complete", engine_name, adapter, flush=True)
        latencies = [sample["native_event_to_commit_end_ms"] for sample in samples]
        return {
            "engine": engine_name,
            "adapter": adapter,
            "cards": card_count,
            "cycles": cycles,
            "warmup": warmup,
            "presentation_feedback_supported": False,
            "frame_rate_fps": None,
            "latency_definition": "native Resize/Configure event to completed Cinnamon commit",
            "mean_event_to_commit_ms": statistics.mean(latencies),
            "p95_event_to_commit_ms": percentile(latencies, 95),
            "p99_event_to_commit_ms": percentile(latencies, 99),
            "samples": samples,
        }
    finally:
        if adapter == "qt" and native_observer is not None:
            try:
                native.removeEventFilter(native_observer)
            except RuntimeError:
                pass
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
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    if args.cards < 1 or args.cycles < 1 or args.warmup < 0:
        parser.error("Cards and cycles must be positive and warmup nonnegative")
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    adapters = ("qt", "tk") if args.adapter == "both" else (args.adapter,)
    widths = (680, 760, 800, 900, 1000, 1200, 980, 750)
    print(json.dumps([
        exercise(engine, adapter, args.cards, args.cycles, args.warmup, widths)
        for engine in engines for adapter in adapters
    ], indent=2))


if __name__ == "__main__":
    main()
