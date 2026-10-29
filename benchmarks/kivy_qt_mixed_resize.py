"""1,000 mixed native widgets: Qt/Kivy resize benchmark, Cinnamon Rust/Python.

Use: python benchmarks/kivy_qt_mixed_resize.py --output benchmark-results/mixed-1000
Requires PySide6, Kivy 2.3.x, installed Cinnamon Rust and an actual display.
The results measure native resize-to-layout, NOT compositor presentation FPS.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

WIDTHS = (480, 560, 640, 700, 820, 900, 760, 600, 510)
HEIGHT = 680
KINDS = ("Text", "Button", "Input", "Checkbox", "TextArea", "Slider",
         "Image", "ProgressBar", "Link", "Badge")
BUDGET_MS = 1000 / 60


def percentile(values, percent):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * percent / 100) - 1)]


def scene(image):
    from psx import (Text, Button, Input, Checkbox, TextArea, Slider, Image,
                     ProgressBar, Link, Badge, Flex, Grid, GridItem, Scroll)
    from psx.core.vnode import create_element
    factories = (
        lambda i: Text(f"Metric {i}: responsive label"),
        lambda i: Button(f"Action {i}"),
        lambda i: Input(value=f"query-{i}"),
        lambda i: Checkbox(),
        lambda i: TextArea(f"Note {i}"),
        lambda i: Slider(value=30),
        lambda i: Image(str(image)),
        lambda i: ProgressBar(value=45),
        lambda i: Link(label=f"Link {i}"),
        lambda i: Badge(label=f"Badge {i}"),
    )
    groups = []
    for group in range(100):
        children = []
        for kind, factory in zip(KINDS, factories):
            index = group * len(KINDS) + KINDS.index(kind)
            original = factory(index)
            props = dict(original.props)
            props.update(layout_width="104px", layout_height="26px",
                         flex_basis="104px", flex_shrink=0)
            children.append(create_element(original.type, *original.children,
                                           key=f"leaf-{index:04d}-{kind}", **props))
        groups.append(GridItem(
            Flex(*children, direction="column", gap="3px", width="100%",
                 height="312px", key=f"column-{group}"),
            span=3, key=f"group-{group}"))
    return Flex(
        Scroll(Flex(Grid(*groups, gap="12px", key="grid"), direction="column",
                    width="100%", height="9000px", key="content"),
               direction="vertical", width="100%", height="100%",
               layout_width="100%", layout_height="100%", key="scroll"),
        direction="column", width="100%", height="100%",
        align_items="stretch", key="root")


def viewport(width):
    from psx.sfle.model import AvailableSize, LayoutConstraints
    return LayoutConstraints(AvailableSize(width, True),
                             AvailableSize(HEIGHT, True))


def census(root):
    counts = Counter()
    handles = set()
    nodes = 0
    stack = [root]
    while stack:
        item = stack.pop()
        nodes += 1
        if item.node.type in KINDS:
            counts[item.node.type] += 1
        widget = getattr(getattr(item, "handle", None), "widget", None)
        if widget is not None:
            handles.add(id(widget))
        stack.extend(item.children)
    assert counts == Counter({kind: 100 for kind in KINDS}), counts
    return {"types": dict(counts), "mounted_nodes": nodes,
            "distinct_native_widgets": len(handles)}


def rectangles(renderer):
    result = renderer.sfle_result
    if result is None:
        raise RuntimeError("No committed Cinnamon result")
    return {str(k): [float(b.border.x), float(b.border.y),
                     float(b.border.width), float(b.border.height)]
            for k, b in result.boxes.items()}


def run_cell(adapter, engine_name, warmup, cycles, output, widths):
    from psx.core.reconcile import Reconciler
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.backend import load_layout_engine
    engine = (PythonLayoutEngine() if engine_name == "python"
              else load_layout_engine())
    if engine.backend_name != engine_name:
        raise RuntimeError(f"Refusing Cinnamon fallback: requested {engine_name}, got {engine.backend_name}")
    if adapter == "qt":
        from psx.renderers.qt.pyside import PySide6Renderer
        renderer = PySide6Renderer(argv=["psx-mixed-resize"],
                                   sfle_constraints=viewport(widths[0]), engine=engine)
    else:
        from kivy.config import Config
        Config.set("graphics", "width", str(widths[0]))
        Config.set("graphics", "height", str(HEIGHT))
        from kivy.clock import Clock
        from kivy.core.window import Window
        from psx.renderers.kivy.kivy import KivyRenderer
        renderer = KivyRenderer(sfle_constraints=viewport(widths[0]), engine=engine)
    output.mkdir(parents=True, exist_ok=True)
    image = output / "small.png"
    # Portable minimal valid 1x1 PNG.
    import base64
    image.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91Jpz"
        "AAAAFklEQVR4nGPUrVjAwMDAxMDAwMDAAAAO8wFJy/W0agAAAABJRU5ErkJggg=="))
    tree = Reconciler(renderer)
    events, commits, samples, checks = [], [], [], {}
    observer = None
    native = None
    try:
        mounted = tree.render(scene(image))
        counts = census(mounted)
        native = renderer._sfle_watched_widget
        if native is None:
            raise RuntimeError("Native resize observer is not installed")
        original_commit = renderer.commit_layout

        def timed_commit(root):
            start = time.perf_counter_ns()
            cpu = time.process_time_ns()
            try:
                return original_commit(root)
            finally:
                commits.append((renderer._sfle_constraints.width.value,
                                start, time.perf_counter_ns(),
                                time.process_time_ns() - cpu))
        renderer.commit_layout = timed_commit
        if adapter == "qt":
            core = renderer._qtcore
            qevent = getattr(core.QEvent, "Type", core.QEvent)
            class ResizeObserver(core.QObject):
                def eventFilter(self, watched, event):
                    if watched is native and event.type() == qevent.Resize:
                        events.append((event.size().width(), time.perf_counter_ns()))
                    return False
            observer = ResizeObserver()
            native.installEventFilter(observer)
            native.show()

            def resize(width):
                native.resize(width, HEIGHT)

            def pump():
                renderer.application.processEvents()

            def settled():
                return (not renderer._sfle_resize_scheduled
                        and renderer._sfle_resize_pending is None)
        else:
            from kivy.clock import Clock
            from kivy.core.window import Window
            Window.add_widget(native)
            def on_size(_widget, size):
                events.append((int(round(size[0])), time.perf_counter_ns()))
            native.bind(size=on_size)

            def resize(width):
                Window.size = (width, HEIGHT)
                native.size = (width, HEIGHT)

            def pump():
                Clock.tick()

            def settled():
                return renderer._sfle_resize_pending is None and renderer._sfle_resize_event is None

        pump()
        for index in range(warmup + cycles):
            width = widths[(index + 1) % len(widths)]
            event_start, commit_start = len(events), len(commits)
            requested = time.perf_counter_ns()
            resize(width)
            timeout = time.monotonic() + 6
            while time.monotonic() < timeout:
                pump()
                if (len(commits) > commit_start and settled()
                    and renderer._sfle_constraints.width.value == width):
                    break
                time.sleep(0.001)
            else:
                raise RuntimeError(f"{adapter}/{engine_name}: resize {width} timed out")
            if renderer._sfle_resize_error is not None:
                raise RuntimeError("Native resize failed") from renderer._sfle_resize_error
            observed = [t for w, t in events[event_start:] if w == width]
            committed = [c for c in commits[commit_start:] if c[0] == width]
            if not observed or not committed:
                raise RuntimeError(f"Missing native event/commit for width={width}")
            first_event = observed[0]
            _w, begin, end, cpu = committed[-1]
            if index >= warmup:
                samples.append({
                    "width": width,
                    "request_to_event_ms": (first_event-requested)/1e6,
                    "event_to_commit_ms": (end-first_event)/1e6,
                    "commit_ms": (end-begin)/1e6,
                    "commit_cpu_ms": cpu/1e6,
                    "request_to_settled_ms": (time.perf_counter_ns()-requested)/1e6,
                    "commits": len(committed),
                })
            if width in (480, 640, 820) and width not in checks:
                checks[width] = rectangles(renderer)
        durations = [s["event_to_commit_ms"] for s in samples]
        summary = {f"p{percent}_ms": percentile(durations, percent)
                   for percent in (50, 95, 99)}
        summary.update({
            "over_16_67ms": sum(ms > BUDGET_MS for ms in durations),
            "over_16_67ms_pct": 100 * sum(ms > BUDGET_MS for ms in durations) / len(durations),
            "p95_commit_ms": percentile([s["commit_ms"] for s in samples], 95),
            "p95_settled_ms": percentile([s["request_to_settled_ms"] for s in samples], 95),
            "p95_cpu_ms": percentile([s["commit_cpu_ms"] for s in samples], 95),
            "presentation_frames_dropped": None,
            "presentation_fps": None,
        })
        return {"backend": adapter, "engine": engine_name, "count": counts,
                "cycles": cycles, "warmup": warmup, "summary": summary,
                "samples": samples, "rectangles": checks}
    finally:
        try:
            if adapter == "qt" and observer is not None and native is not None:
                native.removeEventFilter(observer)
            elif adapter == "kivy" and native is not None:
                native.unbind(size=on_size)
                if native.parent is Window:
                    Window.remove_widget(native)
        finally:
            tree.unmount()
            if adapter == "qt":
                renderer.application.processEvents()


def compare(rows, tolerance):
    """Compare rectangle multisets; native object IDs differ across processes."""
    reference = next(row for row in rows if row["backend"] == "qt" and row["engine"] == "python")
    deviations = []
    for row in rows:
        for width, expected in reference["rectangles"].items():
            observed = row["rectangles"].get(width)
            if observed is None:
                deviations.append({"cell": row["backend"] + "/" + row["engine"],
                                   "width": width, "error": "missing checkpoint"})
                continue
            left = sorted(tuple(v) for v in expected.values())
            right = sorted(tuple(v) for v in observed.values())
            if len(left) != len(right):
                deviations.append({"cell": row["backend"] + "/" + row["engine"],
                                   "width": width, "expected_count": len(left),
                                   "observed_count": len(right)})
                continue
            for i, (a, b) in enumerate(zip(left, right)):
                if max(abs(x-y) for x,y in zip(a, b)) > tolerance:
                    deviations.append({"cell": row["backend"] + "/" + row["engine"],
                                       "width": width, "rectangle_index": i,
                                       "expected": a, "actual": b})
    return {"tolerance": tolerance, "differences": deviations[:100],
            "difference_count": len(deviations), "passed": not deviations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=("qt", "kivy", "both"), default="both")
    parser.add_argument("--engine", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--warmup", type=int, default=32)
    parser.add_argument("--cycles", type=int, default=240)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/mixed-1000"))
    parser.add_argument("--tolerance", type=float, default=1)
    args = parser.parse_args()
    if args.warmup < 0 or args.cycles < 100:
        parser.error("warmup >= 0 and at least 100 measured cycles required")
    adapters = ("qt", "kivy") if args.adapter == "both" else (args.adapter,)
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    # Separate native event loops/processes: never mount Qt and Kivy together.
    if len(adapters) * len(engines) > 1:
        for backend in adapters:
            for engine in engines:
                destination = args.output / f"{backend}-{engine}.json"
                command = [sys.executable, str(Path(__file__).resolve()),
                           "--adapter", backend, "--engine", engine,
                           "--warmup", str(args.warmup), "--cycles", str(args.cycles),
                           "--output", str(args.output), "--tolerance", str(args.tolerance)]
                with (args.output / f"{backend}-{engine}.log").open("w") as log:
                    completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
                if completed.returncode:
                    raise SystemExit(f"{backend}/{engine} failed; inspect {backend}-{engine}.log")
                outcomes.append(json.loads(destination.read_text()))
        parity = compare(outcomes, args.tolerance)
        report = {"environment": {"python": sys.version, "os": platform.platform()},
                  "cells": [{k:v for k,v in item.items() if k not in ("samples", "rectangles")}
                            for item in outcomes],
                  "geometry_parity": parity,
                  "note": "Event-to-Cinnamon-commit latency; NOT compositor FPS."}
        (args.output / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        if not parity["passed"]:
            raise SystemExit("Geometry parity failed; see report.json")
        return
    result = run_cell(adapters[0], engines[0], args.warmup, args.cycles,
                      args.output, WIDTHS)
    (args.output / f"{adapters[0]}-{engines[0]}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
