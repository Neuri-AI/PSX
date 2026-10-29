"""60 Hz paced native viewport resize stress for Qt/Kivy and Cinnamon.

Reports missed application scheduling opportunities, NOT displayed/compositor frames.
Each process uses one GUI toolkit and the UI thread for all native work.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from kivy_qt_mixed_resize import scene, viewport, census, BUDGET_MS


def run(adapter, engine_name, frames, output):
    from psx.core.reconcile import Reconciler
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.backend import load_layout_engine
    engine = PythonLayoutEngine() if engine_name == "python" else load_layout_engine()
    if engine.backend_name != engine_name:
        raise RuntimeError(f"Expected Cinnamon {engine_name}, got {engine.backend_name}")
    widths = (480, 560, 640, 700, 820, 900, 760, 600, 510)
    if adapter == "qt":
        from psx.renderers.qt.pyside import PySide6Renderer
        renderer = PySide6Renderer(
            argv=["psx-paced-native-resize"], sfle_constraints=viewport(widths[0]),
            engine=engine)
    else:
        from kivy.config import Config
        Config.set("graphics", "width", str(widths[0]))
        Config.set("graphics", "height", "680")
        from kivy.clock import Clock
        from kivy.core.window import Window
        from psx.renderers.kivy.kivy import KivyRenderer
        renderer = KivyRenderer(sfle_constraints=viewport(widths[0]), engine=engine)
    output.parent.mkdir(parents=True, exist_ok=True)
    import base64
    image = output.parent / "paced-benchmark-image.png"
    image.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91Jpz"
        "AAAAFklEQVR4nGPUrVjAwMDAxMDAwMDAAAAO8wFJy/W0agAAAABJRU5ErkJggg=="))
    tree = Reconciler(renderer)
    native = None
    try:
        root = tree.render(scene(image))
        count = census(root)
        native = renderer._sfle_watched_widget
        if native is None:
            raise RuntimeError("Viewport native watcher not installed")
        if adapter == "qt":
            native.show()
            def resize(width):
                native.resize(width, 680)
            def pump():
                renderer.application.processEvents()
            def pending():
                return renderer._sfle_resize_scheduled or renderer._sfle_resize_pending is not None
        else:
            Window.add_widget(native)
            def resize(width):
                Window.size = (width, 680)
                native.size = (width, 680)
            def pump():
                Clock.tick()
            def pending():
                return renderer._sfle_resize_event is not None or renderer._sfle_resize_pending is not None
        pump()
        interval_ns = 1_000_000_000 / 60
        origin = time.perf_counter_ns()
        dispatched, expired = 0, 0
        data = []
        index = 0
        while index < frames:
            now = time.perf_counter_ns()
            due = int((now - origin) // interval_ns)
            if due < index:
                pump()
                continue
            if due > index:
                expired += min(due - index, frames - index)
                index = min(due, frames)
                if index >= frames:
                    break
            width = widths[index % len(widths)]
            start = time.perf_counter_ns()
            resize(width)
            dispatched += 1
            pump()
            end = time.perf_counter_ns()
            failure = getattr(renderer, "_sfle_resize_error", None)
            if failure is not None:
                raise RuntimeError(f"{adapter}/{engine_name}: native resize failed") from failure
            data.append({
                "slot": index, "width": width,
                "request_to_first_pump_ms": (end - start) / 1e6,
                "commit_pending_after_pump": bool(pending()),
            })
            index += 1
        # Drain pending coalesced native work after the paced sequence.
        deadline = time.monotonic() + 10
        while pending() and time.monotonic() < deadline:
            pump()
        if pending():
            raise RuntimeError("Native resize has not settled after paced sequence")
        failure = getattr(renderer, "_sfle_resize_error", None)
        if failure is not None:
            raise RuntimeError("Final native resize failed") from failure
        return {
            "adapter": adapter, "engine": engine_name,
            "scheduled_slots": frames, "issued_requests": dispatched,
            "skipped_expired_request_slots": expired,
            "missed_application_slot_pct": 100 * expired / frames,
            "budget_ms": BUDGET_MS,
            "presentation_fps": None, "presentation_frames_dropped": None,
            "count": count, "samples": data,
            "note": "Missed scheduling slots are NOT compositor-dropped frames.",
        }
    finally:
        if adapter == "kivy" and native is not None and native.parent is Window:
            Window.remove_widget(native)
        tree.unmount()
        if adapter == "qt":
            renderer.application.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=("qt", "kivy"), required=True)
    parser.add_argument("--engine", choices=("python", "rust"), required=True)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("frames must be positive")
    row = run(args.adapter, args.engine, args.frames, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(row, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in row.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
