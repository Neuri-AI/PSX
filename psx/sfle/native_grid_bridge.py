"""Mounted native Grid bridge shared by the toolkit renderers.

This is deliberately a narrow G3 bridge: a Grid root with direct GridItem
wrappers and one native leaf per wrapper.  Cinnamon computes every item
rectangle; toolkit code only owns parentage, intrinsic reads and rectangle
application/readback.
"""
from __future__ import annotations

from threading import get_ident

from psx.core.layout_tree import normalize_flex_tree
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
        ids = tuple(path_identity(child.path) for child in grid.effective_children)
        item_handles = {path_identity(child.path): handles[id(child.source)]
                        for child in grid.effective_children}
        leaf_nodes = {path_identity(child.path): child.effective_children[0].source
                      for child in grid.effective_children}
        leaf_handles = {identifier: handles[id(node)] for identifier, node in leaf_nodes.items()}
        widgets = {identifier: handle.widget for identifier, handle in leaf_handles.items()}
        if backend is GridCommitBackend.QT:
            from .qt_measurement import QtMeasurementSource
            source = QtMeasurementSource(widgets, qtcore=renderer._qtcore)
        elif backend is GridCommitBackend.TK:
            from .tk_measurement import TkMeasurementSource
            source = TkMeasurementSource(widgets)
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
        prepared = measure_grid_native(
            grid, content_width=float(width), source=source, mounted_ids=ids,
            revisions={identifier: generation for identifier in ids}, generation=generation,
            current_generation=renderer._sfle_generation,
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
        # The root is a native host, but it has no competing layout manager.
        root_widget = handles[id(grid.source)].widget
        if backend is GridCommitBackend.QT:
            root_widget.setGeometry(0, 0, round(width), round(height))
        elif backend is GridCommitBackend.TK:
            root_widget.place(x=0, y=0, width=round(width), height=round(height))
        else:
            root_widget.pos = (0, 0)
            root_widget.size = (width, height)
        receipt = commit_grid_native_geometry(
            tuple(batch), backend=backend, widgets=commit_widgets, generation=generation,
            current_generation=lambda: renderer._sfle_generation,
            is_ui_thread=source.is_ui_thread,
            parent_height=float(height) if backend is GridCommitBackend.KIVY else None,
        )
        renderer.grid_result = (prepared, receipt)
    finally:
        renderer._sfle_in_commit = False
