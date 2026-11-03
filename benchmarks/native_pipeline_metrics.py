"""Scoped phase counters for native resize certification processes."""
from __future__ import annotations

from collections import defaultdict
from functools import wraps
from time import perf_counter_ns


class PipelineMetrics:
    def __init__(self):
        self.elapsed = defaultdict(float)
        self.calls = defaultdict(int)
        self.depth = defaultdict(int)
        self.restorations = []

    def watch(self, owner, name, category):
        original = getattr(owner, name)
        self.elapsed[category] += 0.0
        self.calls[category] += 0

        @wraps(original)
        def measured(*args, **kwargs):
            outer = self.depth[category] == 0
            self.depth[category] += 1
            started = perf_counter_ns() if outer else 0
            try:
                return original(*args, **kwargs)
            finally:
                self.depth[category] -= 1
                if outer:
                    self.calls[category] += 1
                    self.elapsed[category] += (perf_counter_ns() - started) / 1e6

        self.restorations.append((owner, name, original))
        setattr(owner, name, measured)

    def snapshot(self):
        return dict(self.elapsed), dict(self.calls)

    def delta(self, previous):
        elapsed, calls = previous
        categories = set(self.elapsed) | set(elapsed)
        return {category: {
            "elapsed_ms": self.elapsed[category] - elapsed.get(category, 0),
            "calls": self.calls[category] - calls.get(category, 0),
        } for category in sorted(categories)}

    def close(self):
        for owner, name, original in reversed(self.restorations):
            setattr(owner, name, original)
        self.restorations.clear()


def instrument_native_pipeline(renderer, reconciler_type, backend):
    from psx.layout.adapters import native_grid_bridge
    from psx.layout.adapters.native_geometry import NativeGeometryCommitter
    from psx.layout.grid import mixed_grid_native

    metrics = PipelineMetrics()
    for name in ("create", "insert", "update", "move", "remove", "destroy"):
        metrics.watch(renderer, name, "native_" + name)
    metrics.watch(reconciler_type, "_reconcile", "reconciliation")
    metrics.watch(reconciler_type, "_evaluate_component", "component_render")
    metrics.watch(NativeGeometryCommitter, "__call__", "native_geometry_commit")
    metrics.watch(mixed_grid_native, "commit_grid_native_geometry", "native_geometry_commit")
    metrics.watch(native_grid_bridge, "commit_grid_native_geometry", "native_geometry_commit")
    if backend == "qt":
        from psx.renderers.qt.cinnamon_qt_measurement import QtMeasurementSource as Source
    elif backend == "tk":
        from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource as Source
    else:
        from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource as Source
    metrics.watch(Source, "measure", "native_measurement")
    metrics.watch(Source, "measure_width", "native_measurement")
    # Include scratch-label projection in measurement cost. It is structural
    # glyph work on one shared resource, not an update of each P2 widget.
    from psx.layout.runtime.structural_text_probe import StructuralTextProbe
    metrics.watch(StructuralTextProbe, "measure", "native_measurement")
    metrics.watch(Source, "measure", "native_intrinsic_queries")
    metrics.watch(Source, "measure_width", "native_intrinsic_queries")
    return metrics
