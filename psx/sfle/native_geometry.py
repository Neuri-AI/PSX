"""Native geometry adapters for the resolved SFLE rectangle contract.

Boxes use absolute top-left logical coordinates. Qt/Tk widget geometry is
parent-local; Kivy widget positions/canvas instructions use the native window
plane, with a bottom-left Y origin. The root host is adapter-owned.
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
    from .external_native_geometry_ports import SFLEExternalPort
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
        prior_tk_placements: Mapping[str, Mapping[str, object]] | None = None,
        prior_qt_rectangles: Mapping[str, tuple[int, int, int, int]] | None = None,
    ) -> None:
        if not isinstance(backend, GeometryBackend):
            raise TypeError("Expected GeometryBackend.")
        self._backend = backend
        self._skip_unchanged = skip_unchanged
        if prior_tk_placements is not None and backend is not GeometryBackend.TK:
            raise TypeError("Pre-captured Tk placements require the Tk backend.")
        # The caller captured this snapshot on the same UI thread before
        # geometry mutation, for rollback. Reuse it for unchanged checks
        # rather than repeating a Tcl place_info() round trip per child.
        self._prior_tk_placements = (
            {key: dict(info) for key, info in prior_tk_placements.items()}
            if prior_tk_placements is not None else None
        )
        if prior_qt_rectangles is not None and backend is not GeometryBackend.QT:
            raise TypeError("Pre-captured Qt geometry requires the Qt backend.")
        # Captured native rectangles already form the mandatory rollback
        # baseline. Reuse them to check unchanged geometry without another
        # QWidget.geometry() call for each node in the commit batch.
        self._prior_qt_rectangles = (
            dict(prior_qt_rectangles)
            if prior_qt_rectangles is not None else None
        )
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
            from .external_native_geometry_ports import SFLEExternalPort
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
        # Resolve the Kivy canvas origin once; a parent walk for every node
        # would turn the O(N) geometry commit into quadratic work.
        kivy_root = None
        kivy_root_box = None
        if self._backend == GeometryBackend.KIVY:
            root_id = next(node_id for node_id, parent_id in self._parents.items()
                           if parent_id is None)
            kivy_root = self._widgets[root_id]
            kivy_root_box = boxes[root_id]
        for node_id, parent_id in self._parents.items():
            if parent_id is None:
                continue
            if parent_id not in boxes:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing geometry parent.")
            border, parent = boxes[node_id], boxes[parent_id]
            x = (LayoutUnit.from_nearest(border.x) - LayoutUnit.from_nearest(parent.x)).to_px()
            y = (LayoutUnit.from_nearest(border.y) - LayoutUnit.from_nearest(parent.y)).to_px()
            if self._backend == GeometryBackend.KIVY:
                # Kivy Widget.pos and canvas instructions share the native
                # window coordinate plane. Merely nesting widgets does NOT
                # translate their canvas by each ancestor's position.
                # Qt/Tk use parent-local coordinates, but projecting those
                # values into Kivy places every nested Label at (0, 0).
                x = (LayoutUnit.from_nearest(border.x)
                     - LayoutUnit.from_nearest(kivy_root_box.x)).to_px() + float(kivy_root.x)
                y = (LayoutUnit.from_nearest(float(kivy_root.height))
                     - (LayoutUnit.from_nearest(border.y)
                        - LayoutUnit.from_nearest(kivy_root_box.y))
                     - LayoutUnit.from_nearest(border.height)).to_px() + float(kivy_root.y)
            placements.append((node_id, self._widgets[node_id], x, y, border.width, border.height))
        for node_id, widget, x, y, width, height in placements:
            port = self._external_ports.get(node_id)
            if self._skip_unchanged:
                if port is not None:
                    # External Tk read ports may require an initial place()
                    # call before any position attributes exist.
                    already_placed = (
                        self._backend != GeometryBackend.TK
                        or bool(
                            self._prior_tk_placements[node_id]
                            if self._prior_tk_placements is not None
                               and node_id in self._prior_tk_placements
                            else widget.place_info()
                        )
                    )
                    if already_placed:
                        actual = port.read(widget)
                        if (actual.x, actual.y, actual.width, actual.height) == (
                                x, y, width, height):
                            continue
                elif self._backend == GeometryBackend.QT:
                    prior = (
                        self._prior_qt_rectangles.get(node_id)
                        if self._prior_qt_rectangles is not None else None
                    )
                    if prior is None:
                        rect = widget.geometry()
                        prior = (rect.x(), rect.y(), rect.width(), rect.height())
                    if prior == (round(x), round(y), round(width), round(height)):
                        continue
                elif self._backend == GeometryBackend.TK:
                    info = (
                        self._prior_tk_placements[node_id]
                        if self._prior_tk_placements is not None
                           and node_id in self._prior_tk_placements
                        else widget.place_info()
                    )
                    expected = dict(x=round(x), y=round(y),
                                    width=round(width), height=round(height))
                    if info and all(key in info and round(float(info[key])) == value
                                    for key, value in expected.items()):
                        continue
                elif tuple(widget.pos) == (x, y) and tuple(widget.size) == (width, height):
                    continue
            if port is not None:
                port.apply(widget, Rect(x, y, width, height))
            elif self._backend == GeometryBackend.QT:
                widget.setGeometry(round(x), round(y), round(width), round(height))
            elif self._backend == GeometryBackend.TK:
                widget.place(x=round(x), y=round(y), width=round(width), height=round(height))
            else:
                widget.pos = (x, y)
                widget.size = (width, height)
