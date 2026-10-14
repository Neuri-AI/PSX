"""Width-dependent Grid participants inside mounted Flex/Scroll trees.

Cinnamon Flex assigns a Grid content width; Cinnamon Grid independently
measures and places its descendants. Toolkits do not calculate sibling layout.
"""
from __future__ import annotations

from collections.abc import Mapping
from threading import get_ident

from psx.core.grid_contract import GRID_BREAKPOINTS
from psx.core.vnode import NodeKind
from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from .grid_native_composition import prepare_composed_grid, compose_geometry_batch
from .model import IntrinsicSizes, MeasuredBox, LayoutConstraints, AvailableSize
from .native_layout_snapshot import path_identity


class MountedMixedGrid:
    """Transaction-scoped native bridge, never a second layout algorithm."""

    def __init__(self, renderer, normalized, handles: Mapping[int, object],
                 backend: GridCommitBackend, generation: int):
        self.renderer = renderer
        self.handles = handles
        self.backend = backend
        self.generation = generation
        self.breakpoints = getattr(renderer, "_grid_breakpoints", GRID_BREAKPOINTS)
        self.grids = {}

        def visit(node):
            if node.kind is NodeKind.HOST and node.type == "Grid":
                self.grids[path_identity(node.path)] = node
                return
            for child in node.effective_children:
                visit(child)

        for root in normalized._participating_roots():
            visit(root)

    def _on_thread(self):
        return get_ident() == self.renderer._sfle_owner_thread

    def compose(self, node_id, width):
        if not self._on_thread() or self.renderer._sfle_generation != self.generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Mixed Grid measurement became stale or left the owner thread.")
        grid = self.grids[node_id]

        def measure_leaf(identifier, node, allocated_width):
            handle = self.handles[id(node.source)]
            if self.backend is GridCommitBackend.QT:
                from .qt_measurement import QtMeasurementSource
                source = QtMeasurementSource(
                    {identifier: handle.widget}, qtcore=self.renderer._qtcore)
            elif self.backend is GridCommitBackend.TK:
                from .tk_measurement import TkMeasurementSource
                source = TkMeasurementSource({identifier: handle.widget})
                self.renderer.root.update_idletasks()
            elif self.backend is GridCommitBackend.KIVY:
                from .kivy_measurement import KivyMeasurementSource
                refresh = getattr(handle.widget, "texture_update", None)
                if callable(refresh):
                    refresh()
                source = KivyMeasurementSource({identifier: handle.widget})
            else:
                raise GridPackingError("Mixed native Grid requires a toolkit backend.")
            result = source.measure_width(identifier, allocated_width)
            if not isinstance(result, IntrinsicSizes):
                raise GridPackingError("Mixed Grid needs measured terminal native leaves.")
            return result

        return prepare_composed_grid(
            grid, content_width=width,
            generation=self.generation,
            current_generation=self.renderer._sfle_generation,
            measure_leaf=measure_leaf, is_ui_thread=self._on_thread,
            breakpoints=self.breakpoints,
        )

    def intrinsic(self, node_id, width):
        measured = self.compose(node_id, width)
        return IntrinsicSizes(0, width, 0, measured.content_height,
                              width, measured.content_height)

    def seed_measurements(self):
        if not self.grids:
            return ()
        axis = self.renderer._sfle_constraints.width
        if not axis.definite or axis.value is None:
            raise GridPackingError("Mixed Grid requires an initial definite viewport width.")
        return tuple(MeasuredBox(
            node_id, self.intrinsic(node_id, axis.value),
            LayoutConstraints(AvailableSize(None, False),
                              AvailableSize(None, False)),
            self.generation,
        ) for node_id in self.grids)

    def width_dependencies(self):
        return {node_id: (lambda width, node_id=node_id:
                          self.intrinsic(node_id, width))
                for node_id in self.grids}

    def plan(self, boxes):
        prepared = []
        for node_id in self.grids:
            box = boxes[node_id].content
            composition = self.compose(node_id, box.width)
            batch, widgets, heights = compose_geometry_batch(
                composition,
                handles={identity: handle.widget
                         for identity, handle in self.handles.items()},
                root_height=box.height,
            )
            prepared.append((composition, batch, widgets, heights, box.height))
        return tuple(prepared)

    def _descendants(self):
        visited = {}
        def visit(node):
            if node.kind in (NodeKind.HOST, NodeKind.NATIVE):
                widget = self.handles[id(node.source)].widget
                visited[id(widget)] = widget
            for child in node.effective_children:
                visit(child)
        for node in self.grids.values():
            visit(node)
        return visited.values()

    def snapshot(self):
        result = []
        for widget in self._descendants():
            if self.backend is GridCommitBackend.QT:
                r = widget.geometry()
                state = (r.x(), r.y(), r.width(), r.height())
            elif self.backend is GridCommitBackend.TK:
                state = dict(widget.place_info())
            else:
                state = (tuple(widget.pos), tuple(widget.size))
            result.append((widget, state))
        return tuple(result)

    def restore(self, previous):
        for widget, state in reversed(previous):
            if self.backend is GridCommitBackend.QT:
                widget.setGeometry(*state)
            elif self.backend is GridCommitBackend.TK:
                if state:
                    widget.place_configure(**state)
                else:
                    widget.place_forget()
            else:
                widget.pos, widget.size = state

    def commit(self, plans):
        receipts = []
        for composition, batch, widgets, heights, root_height in plans:
            receipt = commit_grid_native_geometry(
                batch, backend=self.backend, widgets=widgets,
                generation=self.generation,
                current_generation=lambda: self.renderer._sfle_generation,
                is_ui_thread=self._on_thread,
                parent_height=(root_height
                               if self.backend is GridCommitBackend.KIVY else None),
                parent_heights=(heights
                                if self.backend is GridCommitBackend.KIVY else None),
            )
            receipts.append((composition.prepared, receipt))
        return receipts
