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
from psx import Grid, GridItem, Flex, Text, Button, psx
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine


def percentile(values, percentage):
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * percentage + 99) // 100 - 1)]


def build_workload(count, scenario, *, styled=False):
    """Independent UI shapes, not only the benchmark's six rounded cards."""
    if scenario == "cards":
        return cards(count, styled=styled)
    if scenario == "controls":
        return Grid(*(
            GridItem(Flex(
                Text(f"Settings row {i}", key="label"),
                Button(f"Apply {i}", key="action"),
                Text(f"Value {i * 17}", key="value"),
                direction="column", gap="8px",
            ), key=f"row-{i}")
            for i in range(count)
        ), gap="16px")
    if scenario in ("flow", "dense-flow"):
        children = "".join(
            f'<p key="label-{i}">Row {i}: responsive content</p>'
            f'<button key="action-{i}">Apply {i}</button>'
            for i in range(count)
        )
        if scenario == "dense-flow":
            # One GridItem contains N Flow children; exercises the previously
            # quadratic parent lookup and the single large subtree case.
            return psx(f'<div><Grid><GridItem span="12"><div>{children}</div></GridItem></Grid></div>')
        return psx(f"<div>{children}</div>")
    raise ValueError(f"Unknown native scaling scenario: {scenario}")


def mounted_stats(root):
    """Count actual mounted nodes/handles, not just logical rows or cards."""
    nodes, handles = 0, set()
    stack = [root]
    while stack:
        instance = stack.pop()
        nodes += 1
        handle = getattr(instance, "handle", None)
        widget = getattr(handle, "widget", None)
        if widget is not None:
            handles.add(id(widget))
        stack.extend(instance.children)
    return nodes, len(handles)


def exercise(engine_name, adapter, card_count, cycles, warmup, widths, *, styled=False, scenario="cards"):
    engine = PythonLayoutEngine() if engine_name == "python" else load_layout_engine()
    if engine.backend_name != engine_name:
        raise RuntimeError(f"Expected Cinnamon {engine_name}, got {engine.backend_name}")
    if adapter == "qt":
        from psx.renderers.qt.pyside import PySide6Renderer
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
    tk_observer_tag = None
    tk_observer_commands = ()
    try:
        mounted = tree.render(build_workload(card_count, scenario, styled=styled))
        mounted_nodes, native_widgets = mounted_stats(mounted)
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
            # Tk toplevel bindtags are inherited by all descendants. A
            # normal root.bind("<Configure>") observer would manufacture a
            # Python Event for *every* child Canvas/Frame geometry change,
            # artificially slowing the workload being benchmarked.
            tk_observer_tag = f"PSXBenchRoot_{id(native)}"
            native.bindtags((tk_observer_tag, *native.bindtags()))
            tk_observer_commands = (
                native.bind_class(
                    tk_observer_tag, "<Configure>",
                    lambda event: events.append((event.width, time.perf_counter_ns())),
                ),
                native.bind_class(
                    tk_observer_tag, "<Expose>",
                    lambda _event: paints.append(time.perf_counter_ns()),
                ),
            )
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
            cpu_started = time.process_time_ns()
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
            failure = getattr(renderer, "_sfle_resize_error", None)
            if failure is not None:
                raise RuntimeError("Native resize layout failed") from failure
            finished_at = time.perf_counter_ns()
            cpu_ms = (time.process_time_ns() - cpu_started) / 1e6
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
                    "request_to_loop_settled_cpu_ms": cpu_ms,
                    "paint_notifications": len(paints) - paint_count,
                    "commits": len(matching),
                })
        latencies = [sample["native_event_to_commit_end_ms"] for sample in samples]
        return {
            "engine": engine_name,
            "adapter": adapter,
            "cards": card_count,
            "scenario": scenario,
            "logical_items": card_count,
            "mounted_nodes": mounted_nodes,
            "native_widgets": native_widgets,
            "cycles": cycles,
            "warmup": warmup,
            "styled": styled,
            "presentation_feedback_supported": False,
            "frame_rate_fps": None,
            "latency_definition": "native Resize/Configure event to completed Cinnamon commit",
            "mean_event_to_commit_ms": statistics.mean(latencies),
            "p95_event_to_commit_ms": percentile(latencies, 95),
            "p99_event_to_commit_ms": percentile(latencies, 99),
            "mean_request_to_loop_settled_ms": statistics.mean(
                sample["request_to_loop_settled_ms"] for sample in samples),
            "p95_request_to_loop_settled_ms": percentile(
                [sample["request_to_loop_settled_ms"] for sample in samples], 95),
            "mean_request_to_loop_settled_cpu_ms": statistics.mean(
                sample["request_to_loop_settled_cpu_ms"] for sample in samples),
            "samples": samples,
        }
    finally:
        if adapter == "qt" and native_observer is not None:
            try:
                native.removeEventFilter(native_observer)
            except RuntimeError:
                pass
        if adapter == "tk" and tk_observer_tag is not None:
            native.unbind_class(tk_observer_tag, "<Configure>")
            native.unbind_class(tk_observer_tag, "<Expose>")
            native.bindtags(tuple(
                tag for tag in native.bindtags() if tag != tk_observer_tag
            ))
            for command in tk_observer_commands:
                if command:
                    native.deletecommand(command)
        tree.unmount()
        if adapter == "qt":
            renderer.application.processEvents()
        else:
            renderer.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("python", "rust", "both"), default="both")
    parser.add_argument("--adapter", choices=("qt", "tk", "both"), default="both")
    parser.add_argument("--cards", type=int, default=24)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--scenario", choices=("cards", "controls", "flow", "dense-flow"), default="cards",
                        help="Independent native UI workloads (count is logical items)")
    parser.add_argument("--styled", action="store_true",
                        help="Include CSS rounded cards and native repaint work")
    args = parser.parse_args()
    if args.cards < 1 or args.cycles < 1 or args.warmup < 0:
        parser.error("Cards and cycles must be positive and warmup nonnegative")
    engines = ("python", "rust") if args.engine == "both" else (args.engine,)
    adapters = ("qt", "tk") if args.adapter == "both" else (args.adapter,)
    widths = (680, 760, 800, 900, 1000, 1200, 980, 750)
    print(json.dumps([
        exercise(engine, adapter, args.cards, args.cycles, args.warmup, widths,
                 styled=args.styled, scenario=args.scenario)
        for engine in engines for adapter in adapters
    ], indent=2))


if __name__ == "__main__":
    main()
