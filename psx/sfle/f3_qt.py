"""G2 Qt: commit SFLE-computed rectangles to actual mounted widgets.

This bridge does NOT implement CSS sizing. Native Qt sizeHint/heightForWidth
supplies intrinsic measurements; SFLE Rust/Python computes all layout boxes.
F2 NativeGeometryCommitter projects absolute top-left rectangles to the
real native parent before writing QWidget.setGeometry.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import NodeKind
from psx.sfle.adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.f3_snapshot import prepare_f3_snapshot
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.qt_measurement import QtMeasurementSource

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.qt.pyqt import QtRenderer


def commit_qt_sfle(renderer: "QtRenderer", root: "MountedInstance") -> None:
    """Measure/compute/validate/apply/read back one current mounted Qt tree."""
    if renderer._sfle_constraints is None:
        return
    if renderer._qtcore.QThread.currentThread() != renderer.application.thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Qt SFLE geometry commit requires the QApplication UI thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Re-entrant Qt SFLE transaction.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        components: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Qt node in SFLE tree.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Component must have one rendered root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Qt handle missing.")
                if id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate mounted VNode.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        prepared = prepare_f3_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        bindings = {node_id: handles[id(node)] for node_id, node in prepared.identities}
        # A Qt layout must never be allowed to override SFLE rectangles.
        for node_id, handle in bindings.items():
            if handle.layout is not None or handle.widget.layout() is not None:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                "Qt SFLE participant is owned by a competing QLayout.", node_id)
        for node in prepared.snapshot.nodes:
            if node.parent_id is None:
                continue
            child, parent = bindings[node.node_id].widget, bindings[node.parent_id].widget
            if child.parentWidget() is not parent:
                raise SFLEError(DiagnosticCode.INVALID_TREE,
                                "Actual Qt parent does not match SFLE parent.", node.node_id)

        leaf_widgets = {
            node_id: bindings[node_id].widget
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST and source.type != "Flex"
        }
        source = QtMeasurementSource(leaf_widgets, qtcore=renderer._qtcore)
        if not source.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt intrinsic measurement requires widget owner thread.")
        measurements = []
        for node_id in leaf_widgets:
            measurements.append(source.measure(MeasurementRequest(
                node_id, renderer._sfle_constraints, generation, generation,
            )))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt measurement generation.")
        snapshot = replace(prepared.snapshot, measurements=tuple(measurements))
        result = renderer._sfle_engine.compute(snapshot)

        ports = SFLEAdapterPorts(
            current_generation=lambda: renderer._sfle_generation,
            nodes_alive=lambda ids: all(
                node_id in bindings and bindings[node_id].widget is not None
                for node_id in ids
            ),
            apply_rectangles=lambda _: None,
            read_rectangles=lambda: {
                node_id: {
                    "x": float(handle.widget.geometry().x()),
                    "y": float(handle.widget.geometry().y()),
                    "width": float(handle.widget.geometry().width()),
                    "height": float(handle.widget.geometry().height()),
                }
                for node_id, handle in bindings.items()
            },
        )
        validate_adapter_commit(snapshot, result, ports)
        if renderer._sfle_generation != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt geometry result.")

        # F2 projection explicitly skips the root/window (host owned).
        # Parent IDs/rectangles are supplied verbatim from the SFLE snapshot.
        nodes = tuple(
            MarginTreeNode(node.node_id, node.parent_id, 0, 0)
            for node in snapshot.nodes
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.QT, nodes,
            {node_id: handle.widget for node_id, handle in bindings.items()},
        )
        before = {
            node_id: (
                widget.widget.geometry().x(), widget.widget.geometry().y(),
                widget.widget.geometry().width(), widget.widget.geometry().height(),
            )
            for node_id, widget in bindings.items()
            if node_id != snapshot.nodes[0].node_id
        }
        try:
            committer(result)
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt commit.")
            rects = dict(result.boxes)
            maximum = 0.0
            observed = ports.read_rectangles()
            for node in snapshot.nodes:
                if node.parent_id is None:
                    continue
                rect, parent = rects[node.node_id].border, rects[node.parent_id].border
                expected = (rect.x - parent.x, rect.y - parent.y, rect.width, rect.height)
                actual = observed[node.node_id]
                for axis, value in zip(("x", "y", "width", "height"), expected):
                    maximum = max(maximum, abs(actual[axis] - value))
            if maximum > 1.0:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Qt widget geometry readback exceeds 1px tolerance.")
        except BaseException:
            for node_id, values in before.items():
                bindings[node_id].widget.setGeometry(*values)
            raise
        renderer.sfle_result = replace(result, geometry_commit_error=maximum)
    finally:
        renderer._sfle_in_commit = False
