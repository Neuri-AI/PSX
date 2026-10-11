"""F3-G2 mounted Kivy geometry bridge over SFLE's immutable output.

Everything stays on the owning Kivy Clock/UI thread. Intrinsic metrics
are read from actual label textures. The pre-existing F2 committer
transforms each absolute top-left SFLE border rectangle into the *actual*
Kivy parent's bottom-left frame: parent_h - local_y - child_h.
No BoxLayout, size_hint, alternate CSS solver or rewritten SFLE boxes.
"""
from __future__ import annotations

from dataclasses import replace
from threading import get_ident
from typing import TYPE_CHECKING

from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import NodeKind
from psx.sfle.adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.f3_snapshot import prepare_f3_snapshot
from psx.sfle.fixed_point import LayoutUnit
from psx.sfle.kivy_measurement import KivyMeasurementSource
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.kivy.kivy import KivyRenderer


def commit_kivy_sfle(renderer: "KivyRenderer", root: "MountedInstance") -> None:
    """Measure, compute, validate, project, apply and read back live widgets."""
    if renderer._sfle_constraints is None:
        return
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "Kivy SFLE geometry requires the renderer's Clock/UI thread.",
        )
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Re-entrant Kivy SFLE commit.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        component_roots: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Kivy layout node.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Function component needs one mounted root.")
                component_roots[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None or id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing or duplicated Kivy layout handle.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=component_roots)
        prepared = prepare_f3_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        bindings = {node_id: handles[id(source)] for node_id, source in prepared.identities}
        for node in prepared.snapshot.nodes:
            if node.parent_id is None:
                if bindings[node.node_id].widget is not renderer._root:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Kivy SFLE root does not match host.")
                continue
            child = bindings[node.node_id].widget
            parent = bindings[node.parent_id].widget
            if child.parent is not parent:
                raise SFLEError(
                    DiagnosticCode.INVALID_TREE, "Actual Kivy parent differs from SFLE tree.", node.node_id,
                )
            if tuple(child.size_hint) != (None, None) or child.pos_hint:
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Kivy size_hint/pos_hint may not override SFLE geometry.", node.node_id,
                )

        leaf_widgets = {
            node_id: bindings[node_id].widget
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST and source.type != "Flex"
        }
        source = KivyMeasurementSource(leaf_widgets)
        readings = []
        for node_id, widget in leaf_widgets.items():
            # Kivy computes texture_size lazily; force only intrinsic texture
            # update, never a parent/BoxLayout placement pass.
            refresh = getattr(widget, "texture_update", None)
            if callable(refresh):
                refresh()
            readings.append(source.measure(MeasurementRequest(
                node_id, renderer._sfle_constraints, generation, generation,
            )))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Kivy measurement became stale.")
        snapshot = replace(prepared.snapshot, measurements=tuple(readings))
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
                    "x": float(handle.widget.x), "y": float(handle.widget.y),
                    "width": float(handle.widget.width), "height": float(handle.widget.height),
                }
                for node_id, handle in bindings.items()
            },
        )
        validate_adapter_commit(snapshot, result, ports)
        if renderer._sfle_generation != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Kivy SFLE computation became stale.")

        boxes = dict(result.boxes)
        root_id = snapshot.nodes[0].node_id
        root_rect = boxes[root_id].border
        host = bindings[root_id].widget
        if any(abs(got - expected) > 1.0 for got, expected in (
            (host.width, root_rect.width), (host.height, root_rect.height),
        )):
            raise SFLEError(
                DiagnosticCode.LAYOUT_CONSTRAINT,
                f"Kivy root host dimensions must match SFLE root; "
                f"host=({host.width},{host.height}), "
                f"SFLE=({root_rect.width},{root_rect.height}).",
                root_id,
            )
        nodes = tuple(
            MarginTreeNode(node.node_id, node.parent_id, 0, 0)
            for node in snapshot.nodes
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.KIVY, nodes,
            {node_id: handle.widget for node_id, handle in bindings.items()},
        )
        before = {
            node_id: (tuple(handle.widget.pos), tuple(handle.widget.size))
            for node_id, handle in bindings.items() if node_id != root_id
        }
        try:
            # F2 already validates the fixed-point grid and applies a pure
            # parent-relative bottom-left transform in precomputed order.
            committer(result)
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Kivy geometry commit.")
            observed = ports.read_rectangles()
            maximum = 0.0
            for node in snapshot.nodes:
                if node.parent_id is None:
                    continue
                border, parent = boxes[node.node_id].border, boxes[node.parent_id].border
                local_x = (LayoutUnit.from_nearest(border.x) -
                           LayoutUnit.from_nearest(parent.x)).to_px()
                local_y = (LayoutUnit.from_nearest(border.y) -
                           LayoutUnit.from_nearest(parent.y)).to_px()
                projected_y = (LayoutUnit.from_nearest(parent.height) -
                               LayoutUnit.from_nearest(local_y) -
                               LayoutUnit.from_nearest(border.height)).to_px()
                actual = observed[node.node_id]
                for axis, expected in zip(
                    ("x", "y", "width", "height"),
                    (local_x, projected_y, border.width, border.height),
                ):
                    maximum = max(maximum, abs(expected - actual[axis]))
            if maximum > 1.0:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Kivy native readback differs from SFLE projection by more than 1px.",
                )
        except BaseException:
            for node_id, (pos, size) in before.items():
                bindings[node_id].widget.pos = pos
                bindings[node_id].widget.size = size
            raise
        renderer.sfle_result = replace(result, geometry_commit_error=maximum)
    finally:
        renderer._sfle_in_commit = False
