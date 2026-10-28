"""Mounted native Grid bridge shared by the toolkit renderers.

This is deliberately a narrow G3 bridge: a Grid root with direct GridItem
wrappers and one native leaf per wrapper.  Cinnamon computes every item
rectangle; toolkit code only owns parentage, intrinsic reads and rectangle
application/readback.
"""
from __future__ import annotations

from threading import get_ident

from psx.core.layout_tree import normalize_flex_tree
from psx.core.grid_contract import GRID_BREAKPOINTS
from psx.core.vnode import NodeKind

from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from .grid_native_measurement import measure_grid_native
from .grid_native_plan import GridNativePlacement
from .native_layout_snapshot import path_identity


def is_mounted_native_grid_root(root: object) -> bool:
    node = root
    while node.node.kind is NodeKind.COMPONENT and len(node.children) == 1:
        node = node.children[0]
    return node.node.kind is NodeKind.HOST and node.node.type == "Grid"


def commit_native_grid(renderer: object, root: object, *, backend: GridCommitBackend) -> None:
    """Commit a reconciled native Grid without a toolkit layout manager."""
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Grid commit requires the renderer UI thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Reentrant Grid geometry commit.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        from .grid_intrinsic_reuse import GridIntrinsicReuse
        reuse = getattr(renderer, '_psx_grid_intrinsic_reuse', None)
        if reuse is None:
            reuse = GridIntrinsicReuse()
            renderer._psx_grid_intrinsic_reuse = reuse
        reuse_transaction = reuse.begin(invalidation_epoch)
        components, handles = {}, {}

        def gather(instance):
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Grid instance.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Grid component needs one root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None or id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing or reused Grid handle.")
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
        if (not renderer._sfle_constraints.width.definite or width is None
                or not renderer._sfle_constraints.height.definite or height is None):
            raise GridPackingError("Grid root requires definite viewport constraints.")
        nested_content = any(
            child.effective_children and child.effective_children[0].type in ("Grid", "Flex", "Scroll")
            for child in grid.effective_children
        )
        composed_heights = None
        if nested_content:
            # Each nested Grid resolves spans at its own Cinnamon-allocated
            # content width; native sources measure only terminal widgets.
            from .grid_native_composition import (
                prepare_composed_grid, compose_geometry_batch,
            )
            if backend is GridCommitBackend.TK:
                renderer.root.update_idletasks()

            def measure_leaf(identifier, node, allocated_width):
                widget = handles[id(node.source)].widget
                if backend is GridCommitBackend.QT:
                    from .qt_measurement import QtMeasurementSource
                    native_source = QtMeasurementSource(
                        {identifier: widget}, qtcore=renderer._qtcore)
                elif backend is GridCommitBackend.TK:
                    from .tk_measurement import TkMeasurementSource
                    native_source = TkMeasurementSource({identifier: widget}, idle_synced=True)
                elif backend is GridCommitBackend.KIVY:
                    from .kivy_measurement import KivyMeasurementSource
                    refresh = getattr(widget, "texture_update", None)
                    if callable(refresh):
                        refresh()
                    native_source = KivyMeasurementSource({identifier: widget})
                else:
                    raise AssertionError("Unexpected native Grid backend.")
                return reuse_transaction.measure(
                    backend.value, widget, node, allocated_width,
                    lambda: native_source.measure_width(identifier, allocated_width),
                )

            composed = prepare_composed_grid(
                grid, content_width=float(width), generation=generation,
                current_generation=renderer._sfle_generation,
                measure_leaf=measure_leaf,
                is_ui_thread=lambda: get_ident() == renderer._sfle_owner_thread,
                breakpoints=getattr(renderer, "_grid_breakpoints", GRID_BREAKPOINTS),
                engine=renderer._sfle_engine,
                viewport_constraints=renderer._sfle_constraints,
            )
            prepared = composed.prepared
            batch, commit_widgets, composed_heights = compose_geometry_batch(
                composed, handles={identity: handle.widget
                                   for identity, handle in handles.items()},
                root_height=float(height),
            )
            from types import SimpleNamespace
            source = SimpleNamespace(
                is_ui_thread=lambda: get_ident() == renderer._sfle_owner_thread)
        else:
            ids = tuple(path_identity(child.path) for child in grid.effective_children)
            item_handles = {path_identity(child.path): handles[id(child.source)]
                            for child in grid.effective_children}
            leaf_nodes = {path_identity(child.path): child.effective_children[0].source
                          for child in grid.effective_children}
            leaf_handles = {identifier: handles[id(node)]
                            for identifier, node in leaf_nodes.items()}
            widgets = {identifier: handle.widget for identifier, handle in leaf_handles.items()}
            if backend is GridCommitBackend.QT:
                from .qt_measurement import QtMeasurementSource
                source = QtMeasurementSource(widgets, qtcore=renderer._qtcore)
            elif backend is GridCommitBackend.TK:
                from .tk_measurement import TkMeasurementSource
                source = TkMeasurementSource(widgets, idle_synced=True)
                renderer.root.update_idletasks()
            elif backend is GridCommitBackend.KIVY:
                from .kivy_measurement import KivyMeasurementSource
                source = KivyMeasurementSource(widgets)
                for widget in widgets.values():
                    refresh = getattr(widget, "texture_update", None)
                    if callable(refresh):
                        refresh()
            else:
                raise AssertionError("native bridge is only for toolkit backends")
            # The same accepted intrinsic cache also serves the simple Grid
            # path. The source's existing toolkit port retains UI ownership.
            from types import SimpleNamespace
            native_source = source
            leaf_origins = {
                path_identity(child.path): child.effective_children[0]
                for child in grid.effective_children
            }
            def measure_cached_leaf(identifier, allocated_width):
                return reuse_transaction.measure(
                    backend.value, widgets[identifier],
                    leaf_origins[identifier], allocated_width,
                    lambda: native_source.measure_width(identifier, allocated_width),
                )
            source = SimpleNamespace(
                port=native_source.port,
                measure_width=measure_cached_leaf,
                is_ui_thread=native_source.is_ui_thread,
            )
            prepared = measure_grid_native(
                grid, content_width=float(width), source=source, mounted_ids=ids,
                revisions={identifier: generation for identifier in ids},
                generation=generation, current_generation=renderer._sfle_generation,
                breakpoints=getattr(renderer, "_grid_breakpoints", GRID_BREAKPOINTS),
            )
            batch, commit_widgets = list(prepared.placements), {
                identifier: handle.widget for identifier, handle in item_handles.items()
            }
            for placement in prepared.placements:
                leaf_id = placement.node_id + "/leaf"
                batch.append(GridNativePlacement(
                    leaf_id, 0, 0, placement.used_width, placement.used_height,
                    placement.used_width, placement.used_height, False, False,
                ))
                commit_widgets[leaf_id] = leaf_handles[placement.node_id].widget
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            # Native widget creation can synchronously publish an intrinsic
            # invalidation (notably Tk's requested-size update).  Renderers
            # recognise this diagnostic as retryable and measure again using
            # the new epoch instead of publishing a stale Grid transaction.
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT,
                "Stale semantic invalidation during Grid intrinsic measurement.",
            )
        # One transaction must cover the root AND every nested native child.
        # A semantic invalidation after successful child readback still needs
        # to restore the already-written children.
        from .mixed_grid_native import MountedMixedGrid
        rollback_scope = MountedMixedGrid(renderer, normalized, handles, backend, generation)
        previous_descendants = rollback_scope.snapshot()
        from .native_scroll_transaction import capture_scroll_hosts, restore_scroll_hosts
        scroll_before = capture_scroll_hosts(backend.value, handles)
        # Capture root geometry before ANY native write. Child transaction
        # rollback alone is insufficient if commit/readback fails after resize.
        root_widget = handles[id(grid.source)].widget
        # A root Grid may itself be the application's top-level QWidget.  Its
        # geometry is owned by the window manager/user, not by the child Grid
        # transaction.  Calling setGeometry(0, 0, ...) here during a resize
        # moves the window to the desktop origin and creates a resize feedback
        # loop. Embedded Grid roots still need their local (0, 0) rectangle.
        top_level_qt = backend is GridCommitBackend.QT and bool(
            getattr(root_widget, "isWindow", lambda: False)()
        )
        if backend is GridCommitBackend.QT:
            previous_rect = root_widget.geometry()
            previous_root = (previous_rect.x(), previous_rect.y(),
                             previous_rect.width(), previous_rect.height())
        elif backend is GridCommitBackend.TK:
            previous_root = dict(root_widget.place_info())
        else:
            previous_root = (tuple(root_widget.pos), tuple(root_widget.size))
        kivy_heights = None
        if backend is GridCommitBackend.KIVY:
            kivy_heights = composed_heights if composed_heights is not None else {
                placement.node_id: float(height) for placement in prepared.placements}
            if composed_heights is None:
                kivy_heights.update({placement.node_id + "/leaf": placement.height
                                     for placement in prepared.placements})
        try:
            # This host never delegates sibling geometry to toolkit layout.
            if backend is GridCommitBackend.QT and not top_level_qt:
                desired = (0, 0, round(width), round(height))
                if previous_root != desired:
                    root_widget.setGeometry(*desired)
            elif backend is GridCommitBackend.TK:
                desired = (0, 0, round(width), round(height))
                if not previous_root or any(
                    int(previous_root[axis]) != value
                    for axis, value in zip(("x", "y", "width", "height"), desired)
                ):
                    root_widget.place(x=0, y=0, width=desired[2], height=desired[3])
            elif backend is GridCommitBackend.KIVY:
                if previous_root[0] != (0, 0):
                    root_widget.pos = (0, 0)
                if previous_root[1] != (width, height):
                    root_widget.size = (width, height)
            receipt = commit_grid_native_geometry(
                tuple(batch), backend=backend, widgets=commit_widgets, generation=generation,
                current_generation=lambda: (renderer._sfle_generation
                    if renderer._sfle_measurement_invalidations.epoch == invalidation_epoch
                    else -1),
                is_ui_thread=source.is_ui_thread,
                parent_height=float(height) if backend is GridCommitBackend.KIVY else None,
                parent_heights=kivy_heights,
            )
            if nested_content:
                rollback_scope._bind_nested_scrolls(composed, scroll_before)
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Grid invalidated after native readback.")
        except BaseException:
            restore_scroll_hosts(scroll_before)
            rollback_scope.restore(previous_descendants)
            # Restore the root as well as the child batch; an initially
            # unplaced Tk root must remain unplaced after failed commit.
            if backend is GridCommitBackend.QT and not top_level_qt:
                root_widget.setGeometry(*previous_root)
            elif backend is GridCommitBackend.TK:
                if previous_root:
                    root_widget.place_configure(**previous_root)
                else:
                    root_widget.place_forget()
            elif backend is GridCommitBackend.KIVY:
                root_widget.pos, root_widget.size = previous_root
            raise
        renderer.grid_result = (prepared, receipt)
        reuse_transaction.accept(invalidation_epoch)
    finally:
        renderer._sfle_in_commit = False
