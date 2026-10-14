"""Mounted Headless Grid: real reconciler identities, Cinnamon and atomic readback.

This bridge supports a Grid root containing GridItem wrappers with one
mounted native leaf each. Composite children and nesting fail closed.
"""
from __future__ import annotations

from threading import get_ident

from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import NodeKind
from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from .grid_native_measurement import HeadlessGridMeasurementSource, measure_grid_native
from .grid_native_plan import GridNativePlacement
from .model import Rect
from .native_layout_snapshot import path_identity


def is_mounted_grid_root(root: object) -> bool:
    node = root
    while node.node.kind is NodeKind.COMPONENT and len(node.children) == 1:
        node = node.children[0]
    return node.node.kind is NodeKind.HOST and node.node.type == "Grid"


def commit_headless_grid(renderer: object, root: object) -> None:
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Grid commit requires owner UI thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Reentrant Grid geometry commit.")
    if renderer._sfle_measure is None:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Headless Grid requires explicit width-aware intrinsic measurements.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        components = {}
        handles = {}

        def gather(instance):
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Grid instance.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Grid component needs one root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Missing mounted Grid handle.")
                if id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Reused Grid VNode.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        roots = normalized._participating_roots()
        if len(roots) != 1 or roots[0].type != "Grid":
            raise GridPackingError("Expected one mounted Grid root.")
        grid = roots[0]
        width = renderer._sfle_constraints.width.value
        height = renderer._sfle_constraints.height.value
        if not renderer._sfle_constraints.width.definite or width is None:
            raise GridPackingError("Grid root requires definite viewport width.")
        if not renderer._sfle_constraints.height.definite or height is None:
            raise GridPackingError("Grid root requires definite viewport height.")
        ids = tuple(path_identity(child.path) for child in grid.effective_children)
        leaves = {
            path_identity(child.path): child.effective_children[0].source
            for child in grid.effective_children
        }
        items = {path_identity(child.path): handles[id(child.source)]
                 for child in grid.effective_children}
        leaf_handles = {identifier: handles[id(node)] for identifier, node in leaves.items()}
        if any(handle.destroyed for handle in (*items.values(), *leaf_handles.values())):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Destroyed Grid widget.")
        source = HeadlessGridMeasurementSource(
            leaves, lambda node, width: renderer._sfle_measure(node, width),
        )
        prepared = measure_grid_native(
            grid, content_width=width, source=source, mounted_ids=ids,
            revisions={identifier: generation for identifier in ids},
            generation=generation, current_generation=renderer._sfle_generation,
        )
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Grid measurement epoch.")
        # A GridItem is a real mounted layout wrapper. Its child receives
        # local (0,0) geometry, using the used size to preserve overflow.
        batch = list(prepared.placements)
        widget_map = dict(items)
        for placement in prepared.placements:
            leaf_id = placement.node_id + "/leaf"
            batch.append(GridNativePlacement(
                leaf_id, 0, 0, placement.used_width, placement.used_height,
                placement.used_width, placement.used_height, False, False,
            ))
            widget_map[leaf_id] = leaf_handles[placement.node_id]
        receipt = commit_grid_native_geometry(
            tuple(batch), backend=GridCommitBackend.HEADLESS,
            widgets=widget_map, generation=generation,
            current_generation=lambda: (renderer._sfle_generation
                                        if renderer._sfle_measurement_invalidations.epoch == invalidation_epoch
                                        else -1),
            is_ui_thread=lambda: get_ident() == renderer._sfle_owner_thread,
        )
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated after readback.")
        grid_handle = handles[id(grid.source)]
        grid_handle.geometry = Rect(0, 0, width, height)
        renderer.grid_result = (prepared, receipt)
    finally:
        renderer._sfle_in_commit = False
