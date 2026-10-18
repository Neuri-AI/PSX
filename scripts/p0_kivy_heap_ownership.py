"""P0 C07: bounded Kivy heap/referrer profiling and direct-Kivy control.

Run in separate fresh processes:
    xvfb-run -a python scripts/p0_kivy_heap_ownership.py --mode velto --json-out artifacts/velto.json
    xvfb-run -a python scripts/p0_kivy_heap_ownership.py --mode native --json-out artifacts/native.json

The native control approximates the same BoxLayout/Button creation, text update,
event callback binding and teardown. It intentionally omits PSX reconciliation
and Cinnamon; these are *not* equivalent execution workloads.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import json
import sys
import time
import tracemalloc
import weakref
from pathlib import Path
from typing import Callable

if __package__:
    from scripts.p0_memory_soak import make_backend, rss_bytes
else:
    from p0_memory_soak import make_backend, rss_bytes


def type_label(value: object) -> str:
    """Exact Python runtime type, never dereferencing a dead weakref proxy."""
    concrete = type(value)
    return f"{concrete.__module__}.{concrete.__qualname__}"


def tracked_type(value: object) -> bool:
    """Limit expensive ownership snapshots to relevant Python allocations."""
    concrete = type(value)
    module = concrete.__module__
    return (
        module.startswith(("psx.", "kivy."))
        or module in {"builtins", "_weakref"}
        and concrete in {dict, list, tuple, weakref.ReferenceType}
    )


def checkpoint_histogram(objects: list[object]) -> dict[str, int]:
    counter = Counter(type_label(item) for item in objects if tracked_type(item))
    return dict(counter.most_common(80))


def referrer_summary(objects: list[object], top: int = 12, samples: int = 3) -> list[dict]:
    """Capture *types* of referrers, never write Python object reprs/identifiers.

    This is exploratory: gc.get_referrers sees local profiler lists/dicts,
    and cannot enumerate ownership in untracked C-level native allocations.
    """
    buckets: dict[str, list[object]] = {}
    for item in objects:
        label = type_label(item)
        if label.startswith(("psx.", "kivy.")):
            bucket = buckets.setdefault(label, [])
            if len(bucket) < samples:
                bucket.append(item)
    output = []
    for label, bucket in sorted(buckets.items(), key=lambda kv: kv[0])[:top]:
        types: Counter[str] = Counter()
        for obj in bucket:
            for ref in gc.get_referrers(obj):
                types[type_label(ref)] += 1
        output.append({
            "object_type": label,
            "sampled_objects": len(bucket),
            "referrer_type_counts": dict(types.most_common(12)),
            "note": "Includes profiler's temporary list/dict references.",
        })
    return output


def make_native_control() -> tuple[
    Callable[[int], tuple[object, object]],
    Callable[[], None], Callable[[], None], Callable[[], None],
]:
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button

    owner = BoxLayout(orientation="vertical", size=(420, 320))
    state: dict[str, object] = {}

    def create(index: int) -> tuple[object, object]:
        layout = BoxLayout(orientation="vertical")
        button = Button(text=f"cycle-{index}")
        callback = lambda *_: None
        button.bind(on_release=callback)
        layout.add_widget(button)
        owner.add_widget(layout)
        button.text = f"updated-{index}"
        state["layout"] = layout
        state["button"] = button
        state["callback"] = callback
        return layout, button

    def release() -> None:
        layout = state.pop("layout", None)
        button = state.pop("button", None)
        callback = state.pop("callback", None)
        if button is not None and callback is not None:
            button.unbind(on_release=callback)
        if layout is not None:
            owner.remove_widget(layout)

    def flush() -> None:
        Clock.tick()

    return create, release, flush, release


def diagnose(mode: str, cycles: int, checkpoints: tuple[int, ...]) -> dict:
    make = make_backend("kivy") if mode == "velto" else make_native_control()
    create, release, flush, close = make
    reports: list[dict] = []
    start = time.perf_counter()
    tracemalloc.start(10)
    try:
        for index in range(1, cycles + 1):
            instance, widget = create(index)
            release()
            del instance, widget
            if index in checkpoints:
                for _ in range(3):
                    flush()
                    gc.collect()
                allocated, peak = tracemalloc.get_traced_memory()
                # Keep the temporary GC inventory out of the RSS/heap sample.
                objects = gc.get_objects()
                histogram = checkpoint_histogram(objects)
                referrers = referrer_summary(objects) if index == cycles else []
                del objects
                reports.append({
                    "cycles": index,
                    "rss_bytes": rss_bytes(),
                    "tracemalloc_current_bytes": allocated,
                    "tracemalloc_peak_bytes": peak,
                    "tracked_type_histogram": histogram,
                    "referrer_samples": referrers,
                    "elapsed_seconds": round(time.perf_counter() - start, 3),
                })
                # Referrer snapshots are diagnostic and may themselves
                # temporarily allocate objects; discard before next cycle.
                del referrers, histogram
        return {
            "mode": mode,
            "cycles": cycles,
            "python": sys.version.split()[0],
            "samples": reports,
            "limitations": [
                "Native is an approximate workload control, not identical to PSX/Cinnamon.",
                "RSS includes toolkit and OpenGL/SDL allocations.",
                "Referrer samples include temporary profiler-owned containers.",
                "GC cannot see all Cython/C-side owners; heap histograms are bounded.",
            ],
        }
    finally:
        tracemalloc.stop()
        close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["velto", "native"], required=True)
    parser.add_argument("--cycles", type=int, default=5000)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    if args.cycles < 3:
        parser.error("--cycles must be >= 3")
    points = (max(1, args.cycles // 10), args.cycles // 2, args.cycles)
    result = diagnose(args.mode, args.cycles, points)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "mode": result["mode"],
        "cycles": args.cycles,
        "rss": [sample["rss_bytes"] for sample in result["samples"]],
        "python_bytes": [
            sample["tracemalloc_current_bytes"] for sample in result["samples"]
        ],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
