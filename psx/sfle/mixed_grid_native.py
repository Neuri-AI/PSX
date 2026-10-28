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
        # Reuse an immutable composition for repeated width requests within
        # one layout transaction. A new MountedMixedGrid is built per commit.
        self._composition_cache = {}

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
        key = (node_id, width)
        if key in self._composition_cache:
            return self._composition_cache[key]
        grid = self.grids[node_id]
        # One native requested-size settlement per composed Grid, not one
        # global Tcl idle drain for every terminal Text widget. Width probes
        # still drain individually if they actually change wraplength.
        if self.backend is GridCommitBackend.TK:
            self.renderer.root.update_idletasks()

        def measure_leaf(identifier, node, allocated_width):
            handle = self.handles[id(node.source)]
            if self.backend is GridCommitBackend.QT:
                from .qt_measurement import QtMeasurementSource
                source = QtMeasurementSource(
                    {identifier: handle.widget}, qtcore=self.renderer._qtcore)
            elif self.backend is GridCommitBackend.TK:
                from .tk_measurement import TkMeasurementSource
                source = TkMeasurementSource(
                    {identifier: handle.widget}, idle_synced=True,
                )
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

        composition = prepare_composed_grid(
            grid, content_width=width,
            generation=self.generation,
            current_generation=self.renderer._sfle_generation,
            measure_leaf=measure_leaf, is_ui_thread=self._on_thread,
            breakpoints=self.breakpoints,
            engine=self.renderer._sfle_engine,
            viewport_constraints=self.renderer._sfle_constraints,
        )
        # Never publish a partial result after a measurement exception.
        self._composition_cache[key] = composition
        return composition

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

    def _bind_nested_scrolls(self, composition, previous):
        from .native_scroll_hosts import (
            apply_kivy_scroll, apply_qt_scroll, apply_tk_scroll,
            binding_from_host,
        )
        from .native_scroll_transaction import prior_scroll_offset
        from .model import Rect

        children = {path_identity(item.path): item
                    for item in composition.grid.effective_children}
        for identifier, (flow, width, height, extent) in composition.nested_scroll.items():
            viewport_node = children[identifier].effective_children[0]
            host = self.handles[id(viewport_node.source)].widget
            if not getattr(host, "_psx_sfle_scroll", False):
                raise GridPackingError("Nested Scroll requires a native Cinnamon viewport.")
            binding = binding_from_host(
                host._psx_props, Rect(0, 0, width, height),
                Rect(0, 0, width, extent),
            )
            offset = prior_scroll_offset(previous, host)
            if self.backend is GridCommitBackend.QT:
                apply_qt_scroll(host, binding, offset)
            elif self.backend is GridCommitBackend.TK:
                apply_tk_scroll(host, binding, offset)
            else:
                apply_kivy_scroll(host, binding, offset)
            for subgrid in flow.nested_grids.values():
                self._bind_nested_scrolls(subgrid, previous)
        for subgrid in composition.nested.values():
            self._bind_nested_scrolls(subgrid, previous)
        for subflow in composition.nested_flow.values():
            for subgrid in subflow.nested_grids.values():
                self._bind_nested_scrolls(subgrid, previous)
        for subflex in composition.nested_flex.values():
            for subgrid in subflex.nested_grids.values():
                self._bind_nested_scrolls(subgrid, previous)

    def commit(self, plans):
        from .native_scroll_transaction import (
            capture_scroll_hosts, restore_scroll_hosts,
        )
        before = self.snapshot()
        scroll_before = capture_scroll_hosts(self.backend.value, self.handles)
        receipts = []
        try:
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
                self._bind_nested_scrolls(composition, scroll_before)
                receipts.append((composition.prepared, receipt))
        except BaseException:
            restore_scroll_hosts(scroll_before)
            self.restore(before)
            raise
        return receipts
