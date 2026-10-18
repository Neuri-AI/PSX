"""P0 C07 native memory soak probe.

Run from repository root, in a *fresh process for each backend*:
    python scripts/p0_memory_soak.py --backend pyside6 --cycles 1000 --json-out pyside6.json
    xvfb-run -a python scripts/p0_memory_soak.py --backend tkinter --cycles 1000 --json-out tk.json
    xvfb-run -a python scripts/p0_memory_soak.py --backend kivy --cycles 1000 --json-out kivy.json

This is diagnostic instrumentation, not a blanket RSS-based leak oracle.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import time
import tracemalloc
import weakref
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Sample:
    cycles: int
    rss_bytes: int | None
    tracemalloc_current_bytes: int
    tracemalloc_peak_bytes: int
    retained_instances: int
    retained_widgets: int
    elapsed_seconds: float
    last_segment_seconds: float


def rss_bytes() -> int | None:
    """Cross-platform RSS if psutil is present; missing RSS is explicit."""
    try:
        import psutil
    except ImportError:
        return None
    return int(psutil.Process(os.getpid()).memory_info().rss)


def force_quiescence(flush: Callable[[], None]) -> None:
    for _ in range(3):
        flush()
        gc.collect()


def run_soak(
    *, cycles: int, interval: int, create: Callable[[int], tuple[Any, Any]],
    release: Callable[[], None], flush: Callable[[], None],
) -> tuple[list[Sample], int]:
    """Samples live wrappers only after native-event/GC quiescence."""
    instance_refs: list[weakref.ReferenceType[Any]] = []
    widget_refs: list[weakref.ReferenceType[Any]] = []
    samples: list[Sample] = []
    start = previous = time.perf_counter()
    tracemalloc.start()
    try:
        for index in range(1, cycles + 1):
            instance, widget = create(index)
            instance_refs.append(weakref.ref(instance))
            widget_refs.append(weakref.ref(widget))
            # Exercise actual update/reconcile without retaining old callbacks.
            release()
            del instance, widget
            if index % interval == 0 or index == cycles:
                force_quiescence(flush)
                now = time.perf_counter()
                allocated, peak = tracemalloc.get_traced_memory()
                samples.append(Sample(
                    cycles=index, rss_bytes=rss_bytes(),
                    tracemalloc_current_bytes=allocated,
                    tracemalloc_peak_bytes=peak,
                    retained_instances=sum(ref() is not None for ref in instance_refs),
                    retained_widgets=sum(ref() is not None for ref in widget_refs),
                    elapsed_seconds=round(now - start, 6),
                    last_segment_seconds=round(now - previous, 6),
                ))
                previous = now
                # Prune dead references: otherwise the *test* memory grows
                # linearly due to retaining weakref objects.
                instance_refs = [ref for ref in instance_refs if ref() is not None]
                widget_refs = [ref for ref in widget_refs if ref() is not None]
    finally:
        tracemalloc.stop()
    return samples, cycles


def make_backend(backend: str) -> tuple[
    Callable[[int], tuple[Any, Any]], Callable[[], None], Callable[[], None],
    Callable[[], None],
]:
    from psx import Text
    from psx.core.reconcile import Reconciler

    if backend == "pyside6":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QCoreApplication, QEvent
        from psx.renderers.qt.pyside import PySide6Renderer

        renderer = PySide6Renderer(argv=["p0-memory-soak"])
        reconciler = Reconciler(renderer)

        def create(index: int) -> tuple[Any, Any]:
            node = reconciler.render(Text(f"cycle-{index}"))
            # Reconcile a changed value before unmounting the same QWidget.
            reconciler.render(Text(f"updated-{index}"))
            return node, node.handle.widget

        def flush() -> None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            renderer.application.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        return create, reconciler.unmount, flush, lambda: (reconciler.unmount(), flush())

    if backend == "tkinter":
        import tkinter as tk
        from psx.renderers.tkinter import TkinterRenderer

        root = tk.Tk()
        root.withdraw()
        renderer = TkinterRenderer(root=root)
        reconciler = Reconciler(renderer)

        def create(index: int) -> tuple[Any, Any]:
            node = reconciler.render(Text(f"cycle-{index}"))
            reconciler.render(Text(f"updated-{index}"))
            return node, node.handle.widget

        def flush() -> None:
            renderer.flush()
            root.update_idletasks()

        def close() -> None:
            reconciler.unmount()
            renderer.close()
            root.destroy()

        return create, reconciler.unmount, flush, close

    if backend == "kivy":
        from kivy.clock import Clock
        from psx import Flex
        from psx.renderers.kivy.kivy import KivyRenderer
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, LayoutConstraints

        renderer = KivyRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(420, True), AvailableSize(320, True)
            ),
            engine=PythonLayoutEngine(),
        )
        reconciler = Reconciler(renderer)

        def create(index: int) -> tuple[Any, Any]:
            root = reconciler.render(Flex(Text(f"cycle-{index}"), direction="column"))
            child = root.children[0]
            reconciler.render(Flex(Text(f"updated-{index}"), direction="column"))
            return child, child.handle.widget

        def flush() -> None:
            Clock.tick()

        return create, reconciler.unmount, flush, reconciler.unmount

    raise ValueError(f"Unknown backend: {backend}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("pyside6", "tkinter", "kivy"), required=True)
    parser.add_argument("--cycles", type=int, default=1000)
    parser.add_argument("--interval", type=int, default=250)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    if args.cycles < 1 or args.interval < 1:
        parser.error("cycles and interval must be positive")

    create, release, flush, close = make_backend(args.backend)
    try:
        samples, count = run_soak(
            cycles=args.cycles, interval=args.interval,
            create=create, release=release, flush=flush,
        )
    finally:
        close()
    # No universal RSS threshold: native allocators often retain arenas.
    # Stronger invariants are native object and Python instance retention.
    latest = samples[-1]
    report = {
        "backend": args.backend,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "cycles": count,
        "sampling_interval": args.interval,
        "rss_available": latest.rss_bytes is not None,
        "samples": [asdict(item) for item in samples],
        "final_retained_instances": latest.retained_instances,
        "final_retained_widgets": latest.retained_widgets,
        "median_segment_seconds": statistics.median(x.last_segment_seconds for x in samples),
        "status": "investigate_retention" if (
            latest.retained_instances or latest.retained_widgets
        ) else "no_python_wrapper_retention_observed",
        "interpretation": (
            "Native toolkit allocator RSS and tracemalloc are diagnostic. "
            "A flat live-object count does not prove absence of all leaks."
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "backend": args.backend, "cycles": count,
        "status": report["status"], "samples": len(samples),
        "rss_bytes": latest.rss_bytes,
    }))
    return 1 if report["status"] == "investigate_retention" else 0


if __name__ == "__main__":
    raise SystemExit(main())
