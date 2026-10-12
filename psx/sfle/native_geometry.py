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
from .model import LayoutResult, Rect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .f3_external import SFLEExternalPort
from .fixed_point import LayoutUnit


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
        *,
        external_ports: Mapping[str, SFLEExternalPort] | None = None,
        skip_unchanged: bool = False,
    ) -> None:
        if not isinstance(backend, GeometryBackend):
            raise TypeError("Expected GeometryBackend.")
        self._backend = backend
        self._skip_unchanged = skip_unchanged
        self._parents = {node.node_id: node.parent_id for node in nodes}
        if len(self._parents) != len(nodes):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate geometry node.")
        self._widgets = dict(widgets)
        self._external_ports = dict(external_ports or {})
        if not set(self._external_ports) <= set(self._parents):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "External geometry port has no SFLE node.")
        if self._external_ports:
            # Keep the F2 toolkit-worker/core import graph independent of
            # G2 vnode/native modules (avoids core.vnode initialization cycle).
            from .f3_external import SFLEExternalPort
        if any(not isinstance(port, SFLEExternalPort) for port in self._external_ports.values()):
            raise TypeError("External geometry ports must be SFLEExternalPort instances.")
        if nodes and nodes[0].parent_id is not None:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Root must be first.")

    def __call__(self, result: RecursiveMeasurementResult | LayoutResult) -> None:
        """Apply either legacy recursive geometry or the F2 snapshot result."""
        if isinstance(result, RecursiveMeasurementResult):
            boxes = {box.node_id: box.border for box in result.geometry.boxes}
        elif isinstance(result, LayoutResult):
            boxes = {node_id: box.border for node_id, box in result.boxes}
        else:
            raise TypeError("Expected RecursiveMeasurementResult or LayoutResult.")
        if set(boxes) != set(self._parents):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Geometry tree identity mismatch.")
        if any(node_id not in self._widgets for node_id in self._parents if self._parents[node_id] is not None):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Missing native geometry widget.")
        # The solver, not a toolkit, owns fixed-point CSS geometry. A
        # forged or unsnapped output must fail *before* touching any widget.
        # Clamping silently here would conceal a LayoutUnit overflow bug.
        for node_id, rect in boxes.items():
            for axis in ("x", "y", "width", "height"):
                value = getattr(rect, axis)
                if LayoutUnit.from_nearest(value).to_px() != value:
                    raise SFLEError(
                        DiagnosticCode.INVALID_SNAPSHOT,
                        "Native geometry requires signed i32 LayoutUnit coordinates.",
                        node_id,
                    )
        # Check the full input before applying any geometry. Native mutation
        # itself is non-transactional and must remain on the owner UI thread.
        placements = []
        for node_id, parent_id in self._parents.items():
            if parent_id is None:
                continue
            if parent_id not in boxes:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing geometry parent.")
            border, parent = boxes[node_id], boxes[parent_id]
            x = (LayoutUnit.from_nearest(border.x) - LayoutUnit.from_nearest(parent.x)).to_px()
            y = (LayoutUnit.from_nearest(border.y) - LayoutUnit.from_nearest(parent.y)).to_px()
            if self._backend == GeometryBackend.KIVY:
                y = (LayoutUnit.from_nearest(parent.height) - LayoutUnit.from_nearest(y)
                     - LayoutUnit.from_nearest(border.height)).to_px()
            placements.append((node_id, self._widgets[node_id], x, y, border.width, border.height))
        for node_id, widget, x, y, width, height in placements:
            port = self._external_ports.get(node_id)
            if port is not None:
                port.apply(widget, Rect(x, y, width, height))
            elif self._backend == GeometryBackend.QT:
                widget.setGeometry(round(x), round(y), round(width), round(height))
            elif self._backend == GeometryBackend.TK:
                widget.place(x=round(x), y=round(y), width=round(width), height=round(height))
            else:
                widget.pos = (x, y)
                widget.size = (width, height)
