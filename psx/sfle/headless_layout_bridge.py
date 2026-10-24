"""First Native SFLE renderer integration: genuine SFLE geometry in Headless.

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
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
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
        prepared = prepare_native_layout_snapshot(
            normalized, constraints, generation=generation,
        )
        node_handles = {
            node_id: handles[id(source)]
            for node_id, source in prepared.identities
        }
        # Shared, conservative dependency classification. Only Text.color
        # currently qualifies for paint-only reuse; all unknown fields force
        # geometry validation, and nonliteral values disable reuse.
        from psx.sfle.layout_change_effects import partition_dependency_signature

        (layout_signature, paint_signature), signature_safe = (
            partition_dependency_signature(
                tuple(
                    (node_id, str(source.type), id(node_handles[node_id]),
                     source.props)
                    for node_id, source in prepared.identities
                ),
                constraints,
            )
        )
        previous_signature = renderer._sfle_committed_signatures
        if (
            signature_safe
            and renderer.sfle_result is not None
            and previous_signature is not None
            and previous_signature[0] == layout_signature
            and previous_signature[1] != paint_signature
            and not renderer._sfle_measurement_invalidations.needs_commit()
        ):
            # Native paint props are already updated by reconciliation. No
            # layout dependencies changed; avoid solver, intrinsic reads,
            # geometry mutation and native readback for this isolated case.
            renderer._sfle_committed_signatures = (layout_signature, paint_signature)
            return
        # Mixed Flex/Grid uses the existing width-dependent Cinnamon solver.
        # The Grid is one atomic Flex leaf; its own native children are
        # computed independently at the width allocated by Flex.
        from psx.sfle.grid_native_composition import (
            prepare_composed_grid, compose_geometry_batch,
        )
        from psx.sfle.grid_native_commit import GridCommitBackend, commit_grid_native_geometry
        from psx.sfle.model import IntrinsicSizes, AvailableSize, LayoutConstraints
        from psx.sfle.width_dependent_intrinsic_measurement import compute_width_dependent
        from psx.sfle.native_layout_snapshot import path_identity
        from psx.core.grid_contract import GRID_BREAKPOINTS
        grid_nodes = {}

        def gather_grids(node):
            if node.kind is NodeKind.HOST and node.type == "Grid":
                grid_nodes[path_identity(node.path)] = node
                return
            for child in node.effective_children:
                gather_grids(child)

        gather_grids(normalized)
        breakpoints = getattr(renderer, "_grid_breakpoints", GRID_BREAKPOINTS)

        def compose_grid(node_id, width):
            grid = grid_nodes[node_id]
            return prepare_composed_grid(
                grid, content_width=width, generation=generation,
                current_generation=renderer._sfle_generation,
                measure_leaf=lambda item_id, leaf, allocated_width:
                    renderer._sfle_measure(leaf.source, allocated_width),
                is_ui_thread=lambda: get_ident() == renderer._sfle_owner_thread,
                breakpoints=breakpoints,
                engine=renderer._sfle_engine,
                viewport_constraints=renderer._sfle_constraints,
            )

        def intrinsic_grid(node_id, width):
            height = compose_grid(node_id, width).content_height
            return IntrinsicSizes(0, width, 0, height, width, height)

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
                if node_id in grid_nodes:
                    width = constraints.width.value
                    if not constraints.width.definite or width is None:
                        raise SFLEError(DiagnosticCode.LAYOUT_CONSTRAINT,
                                        "Mixed Grid requires a definite initial content width.")
                    intrinsic = intrinsic_grid(node_id, width)
                    metrics.append(MeasuredBox(node_id, intrinsic,
                        LayoutConstraints(AvailableSize(None, False), AvailableSize(None, False)),
                        generation))
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
        # Reuse the prepared identities and canonical item lengths while
        # preserving actual host measurements and the legacy Grid composition.
        snapshot = replace(prepared.css_geometry_snapshot(), measurements=tuple(metrics))
        from psx.sfle.incremental_result_reuse import reuse_unchanged_layout
        cached_result = None
        if not grid_nodes and renderer._sfle_prior_solver_engine is renderer._sfle_engine:
            cached_result = reuse_unchanged_layout(
                renderer._sfle_prior_solver_input,
                renderer._sfle_prior_solver_result,
                snapshot,
                native_measurement_invalidated=invalidations.needs_commit(),
            )
        incremental_engine = getattr(renderer._sfle_engine, "compute_incremental", None)
        can_reuse_contexts = (
            not grid_nodes
            and not invalidations.needs_commit()
            and renderer._sfle_prior_solver_engine is renderer._sfle_engine
            and renderer._sfle_prior_solver_input is not None
            and renderer._sfle_prior_solver_result is not None
            and callable(incremental_engine)
        )
        if cached_result is not None:
            result = cached_result
        elif can_reuse_contexts:
            result = incremental_engine(
                snapshot,
                previous_input=renderer._sfle_prior_solver_input,
                previous_result=renderer._sfle_prior_solver_result,
            )
        elif grid_nodes:
            result = compute_width_dependent(
                renderer._sfle_engine, snapshot,
                {node_id: (lambda width, node_id=node_id: intrinsic_grid(node_id, width))
                 for node_id in grid_nodes},
                current_generation=lambda: renderer._sfle_generation,
            )
        else:
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
        descendants_before = {id(handle): (handle, handle.geometry)
                              for handle in handles.values()}
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation before geometry.")
        try:
            for node_id, rect in placements.items():
                # A paint-only reconciliation may still enter this bridge.
                # Preserve native geometry when the committed rectangle is equal;
                # avoid redundant writes and resize feedback without claiming
                # the solver itself was skipped.
                if before[node_id] != rect:
                    node_handles[node_id].geometry = rect
            grid_receipts = []
            for node_id in grid_nodes:
                box = dict(result.boxes)[node_id].content
                composed = compose_grid(node_id, box.width)
                batch, widget_map, _ = compose_geometry_batch(
                    composed, handles=handles, root_height=box.height)
                receipt = commit_grid_native_geometry(
                    batch, backend=GridCommitBackend.HEADLESS,
                    widgets=widget_map, generation=generation,
                    current_generation=lambda: renderer._sfle_generation,
                    is_ui_thread=lambda: get_ident() == renderer._sfle_owner_thread,
                )
                grid_receipts.append((composed.prepared, receipt))
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
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Stale semantic invalidation during native readback.",
                )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale generation during native readback.")
            if error > 1.0:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Headless SFLE geometry readback exceeded 1px tolerance.",
                )
        except BaseException:
            for node_id, old in before.items():
                node_handles[node_id].geometry = old
            for handle, old in descendants_before.values():
                handle.geometry = old
            raise
        renderer.sfle_result = replace(result, geometry_commit_error=error)
        if grid_nodes:
            renderer.grid_result = grid_receipts[-1]
        # Publish the cache only after the layout and native readback pass.
        renderer._sfle_intrinsic_cache = next_cache
        # Publish only after native commit/readback succeeds. Two immutable
        # receipts maximum, replaced every successful transaction.
        renderer._sfle_prior_solver_input = snapshot if not grid_nodes else None
        renderer._sfle_prior_solver_result = result if not grid_nodes else None
        renderer._sfle_prior_solver_engine = renderer._sfle_engine if not grid_nodes else None
        renderer._sfle_committed_signatures = (
            (layout_signature, paint_signature) if signature_safe else None
        )
    finally:
        renderer._sfle_in_commit = False
