"""First F3-G2 renderer integration: genuine SFLE geometry in Headless.

Only a renderer explicitly configured with an SFLE viewport may use this
bridge. Measurements come from the host, never fabricated from constraints.
The normalizer preserves mounted identities; the Rust/Python engine owns
ALL layout distribution. This module neither reimplements Flex nor imports GUI.
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
from psx.sfle.model import MeasuredBox

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.headless import HeadlessRenderer


def commit_headless_sfle(renderer: "HeadlessRenderer", root: "MountedInstance") -> None:
    """Recompute and apply SFLE rectangles to the *mounted* Headless tree.

    Geometry is not inferred from a native BoxLayout. Every SFLE ID is
    paired with an existing live handle. A bad snapshot/engine generation,
    unsupported measurement, or off-grid coordinate fails before mutation.
    """
    if renderer._sfle_constraints is None:
        return
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "Headless SFLE measurement and geometry commit require the owner UI thread.",
        )
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Re-entrant Headless SFLE geometry commit.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        components: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed mounted component in geometry tree.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(
                        DiagnosticCode.INVALID_TREE,
                        "Function component requires exactly one mounted root.",
                    )
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Missing mounted native handle.")
                if id(instance.node) in handles:
                    raise SFLEError(
                        DiagnosticCode.INVALID_TREE,
                        "One VNode instance cannot be mounted twice in an SFLE tree.",
                    )
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        constraints = renderer._sfle_constraints
        prepared = prepare_f3_snapshot(
            normalized, constraints, generation=generation,
        )
        node_handles = {
            node_id: handles[id(source)]
            for node_id, source in prepared.identities
        }
        metrics: list[MeasuredBox] = []
        next_cache = {}
        invalidations = renderer._sfle_measurement_invalidations
        # Global notifications invalidate every intrinsic entry. A targeted
        # resource/content notification affects only its mounted native leaf;
        # other cached siblings remain valid throughout this transaction.
        invalidate_all = invalidations.invalidate_all
        dirty_widgets = frozenset(invalidations.dirty_widgets)
        if renderer._sfle_measure is not None:
            for node_id, source in prepared.identities:
                if source.kind is NodeKind.HOST and source.type == "Flex":
                    continue
                handle_id = id(node_handles[node_id])
                signature = (dict(source.props), constraints)
                previous = renderer._sfle_intrinsic_cache.get(handle_id)
                if (not invalidate_all and handle_id not in dirty_widgets
                        and previous is not None and previous[0] == signature):
                    intrinsic = previous[1]
                else:
                    intrinsic = renderer._sfle_measure(source)
                next_cache[handle_id] = (signature, intrinsic)
                if intrinsic is not None:
                    metrics.append(MeasuredBox(node_id, intrinsic, constraints, generation))
                if renderer._sfle_generation != generation:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale generation after measurement.")
        snapshot = prepare_f3_snapshot(
            normalized, constraints, generation=generation,
            measurements=tuple(metrics),
        ).snapshot
        result = renderer._sfle_engine.compute(snapshot)
        ports = SFLEAdapterPorts(
            current_generation=lambda: renderer._sfle_generation,
            nodes_alive=lambda ids: all(
                not node_handles[node_id].destroyed for node_id in ids
                if node_id in node_handles
            ) and all(node_id in node_handles for node_id in ids),
            apply_rectangles=lambda value: None,  # Geometry applied below after preflight.
            read_rectangles=lambda: {
                node_id: {
                    "x": handle.geometry.x, "y": handle.geometry.y,
                    "width": handle.geometry.width, "height": handle.geometry.height,
                }
                for node_id, handle in node_handles.items() if handle.geometry is not None
            },
        )
        validate_adapter_commit(snapshot, result, ports)

        # Reuse F2's fixed-point grid contract before any renderer mutation.
        placements = {}
        for node_id, box in result.boxes:
            rect = box.border
            for axis in ("x", "y", "width", "height"):
                value = getattr(rect, axis)
                if LayoutUnit.from_nearest(value).to_px() != value:
                    raise SFLEError(
                        DiagnosticCode.INVALID_SNAPSHOT,
                        "Headless native commit requires signed i32 LayoutUnit geometry.",
                        node_id,
                    )
            placements[node_id] = rect

        before = {node_id: handle.geometry for node_id, handle in node_handles.items()}
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation before geometry.")
        try:
            for node_id, rect in placements.items():
                node_handles[node_id].geometry = rect
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale geometry commit.")
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation after geometry.")
            readback = ports.read_rectangles()
            error = max((
                abs(getattr(rect, axis) - readback[node_id][axis])
                for node_id, rect in placements.items()
                for axis in ("x", "y", "width", "height")
            ), default=0.0)
            if error > 1.0:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Headless SFLE geometry readback exceeded 1px tolerance.",
                )
        except BaseException:
            for node_id, old in before.items():
                node_handles[node_id].geometry = old
            raise
        renderer.sfle_result = replace(result, geometry_commit_error=error)
        # Publish the cache only after the layout and native readback pass.
        renderer._sfle_intrinsic_cache = next_cache
    finally:
        renderer._sfle_in_commit = False
