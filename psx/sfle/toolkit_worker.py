"""Executable Kivy/Tk bindings for the portable SFLE worker transaction."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from .adapter_contract import ScrollViewport
from .errors import DiagnosticCode, SFLEError
from .fixed_point import LayoutUnit
from .kivy_measurement import KivyMeasurementSource
from .margin_tree import MarginTreeNode
from .model import IntrinsicSizes, LayoutInput, LayoutResult
from .native_geometry import GeometryBackend, NativeGeometryCommitter
from .tk_measurement import TkMeasurementSource
from .worker_lifecycle import NativeWorkerLayoutHandle, start_native_worker_layout


def _sub(left: float, *right: float) -> float:
    value = LayoutUnit.from_nearest(left)
    for item in right:
        value -= LayoutUnit.from_nearest(item)
    return value.to_px()


class ToolkitWorkerAdapter:
    """Own measurement, geometry commit/readback and rollback for one tree."""

    def __init__(self, backend: GeometryBackend, nodes: tuple[MarginTreeNode, ...],
                 widgets: Mapping[str, object], *,
                 scroll_viewports: tuple[ScrollViewport, ...] = ()) -> None:
        if backend not in (GeometryBackend.KIVY, GeometryBackend.TK):
            raise ValueError("ToolkitWorkerAdapter supports Kivy and Tk only.")
        self.backend = backend
        self.nodes = nodes
        self.widgets = dict(widgets)
        self.parents = {node.node_id: node.parent_id for node in nodes}
        if set(self.parents) != set(self.widgets):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Toolkit widget map must match the SFLE tree.")
        self.commit = NativeGeometryCommitter(backend, nodes, self.widgets)
        content_roots = {viewport.content_root_id for viewport in scroll_viewports}
        if not content_roots.issubset(self.parents):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Scroll content roots must belong to the SFLE tree.")
        self.managed_roots = {
            node_id for node_id in content_roots if self.parents[node_id] is None
        }
        self.measurement = (KivyMeasurementSource(self.widgets) if backend == GeometryBackend.KIVY
                            else TkMeasurementSource(self.widgets))

    def apply_geometry(self, result: LayoutResult) -> None:
        self.commit(result)
        boxes = dict(result.boxes)
        for node_id in self.managed_roots:
            border = boxes[node_id].border
            widget = self.widgets[node_id]
            if self.backend == GeometryBackend.TK:
                widget.place_configure(width=round(border.width), height=round(border.height))
            else:
                widget.size = (border.width, border.height)

    def nodes_alive(self, node_ids: tuple[str, ...]) -> bool:
        if any(node_id not in self.widgets for node_id in node_ids):
            return False
        if self.backend == GeometryBackend.TK:
            try:
                return all(bool(self.widgets[node_id].winfo_exists()) for node_id in node_ids)
            except Exception:
                return False
        return all(self.widgets[node_id] is not None for node_id in node_ids)

    def _native_local(self, node_id: str) -> tuple[float, float, float, float]:
        widget = self.widgets[node_id]
        if self.backend == GeometryBackend.TK:
            return (float(widget.winfo_x()), float(widget.winfo_y()),
                    float(widget.winfo_width()), float(widget.winfo_height()))
        return float(widget.x), float(widget.y), float(widget.width), float(widget.height)

    def read_rectangles(self) -> dict[str, dict[str, float]]:
        """Read toolkit geometry independently and normalize it to top-left."""
        absolute: dict[str, tuple[float, float, float, float]] = {}
        observed: dict[str, dict[str, float]] = {}
        for node in self.nodes:
            x, y, width, height = self._native_local(node.node_id)
            if node.parent_id is None:
                absolute[node.node_id] = (0.0, 0.0, width, height)
                if node.node_id in self.managed_roots:
                    observed[node.node_id] = {
                        "x": 0.0, "y": 0.0, "width": width, "height": height,
                    }
                continue
            parent_x, parent_y, _, parent_height = absolute[node.parent_id]
            if self.backend == GeometryBackend.KIVY:
                y = _sub(parent_height, y, height)
            absolute_x = (LayoutUnit.from_nearest(parent_x) + LayoutUnit.from_nearest(x)).to_px()
            absolute_y = (LayoutUnit.from_nearest(parent_y) + LayoutUnit.from_nearest(y)).to_px()
            absolute[node.node_id] = (absolute_x, absolute_y, width, height)
            observed[node.node_id] = {
                "x": absolute_x, "y": absolute_y, "width": width, "height": height,
            }
        return observed

    def restore_rectangles(self, rectangles: Mapping[str, Mapping[str, float]]) -> None:
        """Restore a previously observed geometry snapshot in preorder."""
        local_parent: dict[str, tuple[float, float, float, float]] = {}
        root = self.nodes[0]
        _, _, root_width, root_height = self._native_local(root.node_id)
        if root.node_id in self.managed_roots:
            rect = rectangles[root.node_id]
            root_width, root_height = float(rect["width"]), float(rect["height"])
            root_widget = self.widgets[root.node_id]
            if self.backend == GeometryBackend.TK:
                root_widget.place_configure(width=round(root_width), height=round(root_height))
            else:
                root_widget.size = (root_width, root_height)
        local_parent[root.node_id] = (0.0, 0.0, root_width, root_height)
        for node in self.nodes[1:]:
            rect = rectangles[node.node_id]
            parent_x, parent_y, _, parent_height = local_parent[node.parent_id]
            x = _sub(float(rect["x"]), parent_x)
            top = _sub(float(rect["y"]), parent_y)
            width, height = float(rect["width"]), float(rect["height"])
            y = _sub(parent_height, top, height) if self.backend == GeometryBackend.KIVY else top
            widget = self.widgets[node.node_id]
            if self.backend == GeometryBackend.TK:
                widget.place(x=round(x), y=round(y), width=round(width), height=round(height))
            else:
                widget.pos = (x, y)
                widget.size = (width, height)
            local_parent[node.node_id] = (float(rect["x"]), float(rect["y"]), width, height)


def _start(snapshot: LayoutInput, adapter: ToolkitWorkerAdapter, *,
           compute: Callable[[LayoutInput], LayoutResult],
           provisional: Callable[[LayoutInput], LayoutResult],
           current_generation: Callable[[], int], initial_widths: dict[str, float],
           post_to_ui: Callable[[Callable[[], None]], None],
           on_finished: Callable[[LayoutResult | None, Exception | None], None],
           scroll_viewports: tuple[ScrollViewport, ...]) -> NativeWorkerLayoutHandle:
    return start_native_worker_layout(
        snapshot, compute=compute, provisional=provisional,
        measure_on_ui=adapter.measurement.measure_width,
        is_ui_thread=adapter.measurement.is_ui_thread,
        current_generation=current_generation, apply_geometry=adapter.apply_geometry,
        observed_geometry=adapter.read_rectangles,
        restore_geometry=adapter.restore_rectangles, initial_widths=initial_widths,
        post_to_ui=post_to_ui, on_finished=on_finished,
        nodes_alive=adapter.nodes_alive, scroll_viewports=scroll_viewports,
    )


def start_kivy_worker_layout(snapshot: LayoutInput, *, clock: object,
        nodes: tuple[MarginTreeNode, ...], widgets: Mapping[str, object],
        compute: Callable[[LayoutInput], LayoutResult],
        provisional: Callable[[LayoutInput], LayoutResult],
        current_generation: Callable[[], int], initial_widths: dict[str, float],
        on_finished: Callable[[LayoutResult | None, Exception | None], None],
        scroll_viewports: tuple[ScrollViewport, ...] = ()) -> NativeWorkerLayoutHandle:
    adapter = ToolkitWorkerAdapter(GeometryBackend.KIVY, nodes, widgets,
                                   scroll_viewports=scroll_viewports)
    return _start(snapshot, adapter, compute=compute, provisional=provisional,
        current_generation=current_generation, initial_widths=initial_widths,
        post_to_ui=lambda callback: clock.schedule_once(lambda _dt: callback(), 0),
        on_finished=on_finished, scroll_viewports=scroll_viewports)


def start_tk_worker_layout(snapshot: LayoutInput, *, root: object,
        nodes: tuple[MarginTreeNode, ...], widgets: Mapping[str, object],
        compute: Callable[[LayoutInput], LayoutResult],
        provisional: Callable[[LayoutInput], LayoutResult],
        current_generation: Callable[[], int], initial_widths: dict[str, float],
        on_finished: Callable[[LayoutResult | None, Exception | None], None],
        scroll_viewports: tuple[ScrollViewport, ...] = ()) -> NativeWorkerLayoutHandle:
    adapter = ToolkitWorkerAdapter(GeometryBackend.TK, nodes, widgets,
                                   scroll_viewports=scroll_viewports)
    return _start(snapshot, adapter, compute=compute, provisional=provisional,
        current_generation=current_generation, initial_widths=initial_widths,
        post_to_ui=root.after_idle, on_finished=on_finished,
        scroll_viewports=scroll_viewports)
