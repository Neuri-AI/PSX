"""Experimental Qt resize probe.

Usage:
  python tools/benchmarks/qt_resize_probe.py --factory my_bench:make_case --engine rust
  python tools/benchmarks/qt_resize_probe.py --factory my_bench:make_case --engine python

Factory signature: make_case(engine_name: str) -> (app, renderer, root, widget)
The factory must mount an actual PSX tree with the explicitly chosen engine.
This probe measures Qt event-to-commit and subsequent Paint *event* latency;
a Paint event is not a guarantee of GPU presentation. No engine selection
or application construction is guessed here.
"""
from __future__ import annotations

import argparse
import importlib
import json
import statistics
import time
from pathlib import Path


def percentile(samples, p):
    if not samples:
        return None
    values = sorted(samples)
    return values[min(len(values) - 1, max(0, int((len(values) - 1) * p)))]


def report(samples):
    return {
        "count": len(samples),
        "p50_ms": percentile(samples, 0.50),
        "p95_ms": percentile(samples, 0.95),
        "p99_ms": percentile(samples, 0.99),
        "mean_ms": statistics.mean(samples) if samples else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", required=True, help="module:function returning app,renderer,root,widget")
    parser.add_argument("--engine", choices=("rust", "python"), required=True)
    parser.add_argument("--out", type=Path, default=Path("qt-resize-profile.json"))
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    module, separator, function = args.factory.partition(":")
    if not separator:
        parser.error("--factory must be module:function")
    app, renderer, root, widget = getattr(importlib.import_module(module), function)(args.engine)
    engine = getattr(renderer, "_sfle_engine", None)
    if engine is None or getattr(engine, "backend_name", None) != args.engine:
        raise RuntimeError("Factory did not select the requested Cinnamon engine explicitly")
    if not getattr(renderer, "_sfle_mounted_root", None):
        raise RuntimeError("Factory must mount the PSX root before profiling")
    core = renderer._qtcore
    event_types = getattr(core.QEvent, "Type", core.QEvent)
    paint_type = event_types.Paint
    durations = {"solver": [], "commit": [], "event_to_paint": []}
    events = []
    active = {"start": None, "first_paint": False}

    class PaintProbe(core.QObject):
        def eventFilter(self, watched, event):
            if watched is widget and event.type() == paint_type:
                start = active["start"]
                if start is not None and not active["first_paint"]:
                    ms = (time.perf_counter_ns() - start) / 1e6
                    durations["event_to_paint"].append(ms)
                    events.append({"phase": "first_paint_event", "elapsed_ms": ms})
                    active["first_paint"] = True
            return False

    probe = PaintProbe()
    widget.installEventFilter(probe)
    original_commit = renderer.commit_layout

    def timed_commit(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_commit(*args, **kwargs)
        finally:
            ms = (time.perf_counter_ns() - start) / 1e6
            durations["commit"].append(ms)
            events.append({"phase": "commit", "elapsed_ms": ms})

    # Instrument the public renderer transaction; solver timing is captured
    # by a class-level temporary patch because engine instances may not allow
    # attribute assignment (slots). Restore everything in finally.
    renderer.commit_layout = timed_commit
    engine_class = type(engine)
    originals = {}
    for name in ("compute", "compute_incremental", "compute_provisional"):
        original = getattr(engine_class, name, None)
        if not callable(original):
            continue
        originals[name] = original

        def wrapper(self, *pos, __name=name, __orig=original, **kw):
            start = time.perf_counter_ns()
            try:
                return __orig(self, *pos, **kw)
            finally:
                ms = (time.perf_counter_ns() - start) / 1e6
                durations["solver"].append(ms)
                events.append({"phase": __name, "elapsed_ms": ms})

        setattr(engine_class, name, wrapper)

    try:
        app.processEvents()
        width, height = widget.width(), widget.height()
        for index in range(args.steps):
            # Alternating dimensions exercise reflows, not repeated no-op sizes.
            target_width = max(200, width + (120 if index % 2 else -90))
            active["start"] = time.perf_counter_ns()
            active["first_paint"] = False
            widget.resize(target_width, height)
            app.processEvents()
            app.processEvents()
            events.append({"phase": "resize", "index": index, "width": target_width,
                           "paint_observed": active["first_paint"]})
            active["start"] = None
        output = {
            "engine": args.engine, "steps": args.steps,
            "stats": {key: report(value) for key, value in durations.items()},
            "events": events,
            "caveats": [
                "Paint event != display presentation or complete frame",
                "Qt processEvents instrumentation changes event scheduling",
                "Repeat with an onscreen benchmark and uninstrumented control",
            ],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output["stats"], indent=2))
    finally:
        renderer.commit_layout = original_commit
        for name, original in originals.items():
            setattr(engine_class, name, original)
        widget.removeEventFilter(probe)


if __name__ == "__main__":
    main()
