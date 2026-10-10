"""Native geometry adapters for the resolved SFLE rectangle contract.

Boxes use absolute top-left logical coordinates. Toolkit child positions
are relative to their actual native parent; Kivy's vertical origin is
bottom-left. The root host/window is never resized by this adapter.
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from .errors import DiagnosticCode, SFLEError
from .margin_tree import MarginTreeNode
from .recursive_measurement import RecursiveMeasurementResult


class GeometryBackend(str, Enum):
    QT = "qt"
    TK = "tk"
    KIVY = "kivy"


class NativeGeometryCommitter:
    """Apply child border boxes through existing native widgets.

    Widget parentage must match the SFLE tree. Window/root geometry is
    adapter-owned. The UI-thread guard and generation gate are provided by
    NativeLayoutLifecycle; calling this directly requires the same ownership.
    """

    def __init__(
        self,
        backend: GeometryBackend,
        nodes: tuple[MarginTreeNode, ...],
        widgets: Mapping[str, object],
    ) -> None:
        if not isinstance(backend, GeometryBackend):
            raise TypeError("Expected GeometryBackend.")
        self._backend = backend
        self._parents = {node.node_id: node.parent_id for node in nodes}
        if len(self._parents) != len(nodes):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate geometry node.")
        self._widgets = dict(widgets)
        if nodes and nodes[0].parent_id is not None:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Root must be first.")

    def __call__(self, result: RecursiveMeasurementResult) -> None:
        if not isinstance(result, RecursiveMeasurementResult):
            raise TypeError("Expected RecursiveMeasurementResult.")
        boxes = {box.node_id: box.border for box in result.geometry.boxes}
        if set(boxes) != set(self._parents):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Geometry tree identity mismatch.")
        if any(node_id not in self._widgets for node_id in self._parents if self._parents[node_id] is not None):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Missing native geometry widget.")
        # Check the full input before applying any geometry. Native mutation
        # itself is non-transactional and must remain on the owner UI thread.
        placements = []
        for node_id, parent_id in self._parents.items():
            if parent_id is None:
                continue
            if parent_id not in boxes:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing geometry parent.")
            border, parent = boxes[node_id], boxes[parent_id]
            x = border.x - parent.x
            y = border.y - parent.y
            if self._backend == GeometryBackend.KIVY:
                y = parent.height - y - border.height
            placements.append((self._widgets[node_id], x, y, border.width, border.height))
        for widget, x, y, width, height in placements:
            if self._backend == GeometryBackend.QT:
                widget.setGeometry(round(x), round(y), round(width), round(height))
            elif self._backend == GeometryBackend.TK:
                widget.place(x=round(x), y=round(y), width=round(width), height=round(height))
            else:
                widget.pos = (x, y)
                widget.size = (width, height)
