"""Width-dependent Grid participants inside mounted Flex/Scroll trees.

Cinnamon Flex assigns a Grid content width; Cinnamon Grid independently
measures and places its descendants. Toolkits do not calculate sibling layout.
"""
from __future__ import annotations

from collections.abc import Mapping
from threading import get_ident

from psx.core.grid_contract import GRID_BREAKPOINTS
from psx.core.vnode import NodeKind
from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.grid.contracts import GridPackingError
from psx.layout.adapters.grid_native_commit import (
    GridCommitBackend, GridNativeCommitReceipt, commit_grid_native_geometry,
)
from psx.layout.adapters.grid_viewport_workset import (
    GridViewportWorkset, subtree_is_safe_for_root_culling,
)
from psx.layout.grid.grid_native_composition import prepare_composed_grid, compose_geometry_batch
from psx.layout.contracts.model import IntrinsicSizes, MeasuredBox, LayoutConstraints, AvailableSize
from psx.layout.projection.native_layout_snapshot import path_identity


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
        # The outer viewport may clip an ordinary Grid subtree. Never
        # perform root-window culling below a native Scroll owner.
        self._viewport_allowed = {}
        self._viewport_heights = {}
        self._viewport_tops = {}
        self._scroll_ancestors = {}
        self._viewport_batches = ()
        # Reuse an immutable composition for repeated width requests within
        # one layout transaction. A new MountedMixedGrid is built per commit.
        self._composition_cache = {}
        # A mixed Grid bridge lives for exactly one Cinnamon generation.
        # Settle the native request-size baseline once for that transaction;
        # TkMeasurementSource still settles individual width probes when it
        # actually changes wraplength.
        self._tk_idle_synced = False
        # The outer Flex/Block bridge creates a new MixedGrid per transaction.
        # Carry accepted native Text measurements across those transactions:
        # the existing Grid cache already validates widget identity, PSX/CSS
        # content, wrapping width and the semantic invalidation epoch.
        from psx.layout.grid.grid_intrinsic_reuse import GridIntrinsicReuse
        reuse = getattr(renderer, "_psx_grid_intrinsic_reuse", None)
        if reuse is None:
            reuse = GridIntrinsicReuse()
            renderer._psx_grid_intrinsic_reuse = reuse
        self._intrinsic_epoch = renderer._sfle_measurement_invalidations.epoch
        self._intrinsic_reuse = reuse.begin(self._intrinsic_epoch)
        from psx.layout.grid.grid_native_composition import FlowBlueprintReuse
        flow_reuse = getattr(renderer, "_psx_grid_flow_blueprints", None)
        if flow_reuse is None:
            flow_reuse = FlowBlueprintReuse()
            renderer._psx_grid_flow_blueprints = flow_reuse
        self._flow_reuse = flow_reuse
        flow_reuse.solved.begin(generation, self._intrinsic_epoch)
        # Reuse certified *whole Grid compositions* before native intrinsic
        # measurement, recursive Flow solves or placement generation. The
        # mounted structural projection already proves VNode/CSS/handle
        # identity, and the semantic epoch fences native font measurements.
        from psx.layout.grid.grid_geometry_reuse import AcceptedGridGeometryReuse
        geometry_reuse = getattr(renderer, "_psx_accepted_grid_geometry", None)
        if geometry_reuse is None:
            geometry_reuse = AcceptedGridGeometryReuse()
            renderer._psx_accepted_grid_geometry = geometry_reuse
        self._geometry_reuse = geometry_reuse
        self._geometry_reuse.begin(
            normalized, self._intrinsic_epoch, backend.value,
            getattr(renderer, "_psx_css_pixel_scale", 1.0)
                if backend is GridCommitBackend.KIVY else 1.0,
            self.breakpoints,
        )

        def visit(node, clip_safe=True, scroll_ancestor=None):
            # Transforms/fixed positioning can escape a native Scroll clip.
            # A genuine Scroll is itself a valid clipping owner; its live
            # offset must be included in every workset decision.
            source = getattr(node, "source", None)
            props = getattr(source, "props", {}) or {}
            style = props.get("style")
            suspicious = ("transform", "filter", "position", "sticky",
                          "fixed", "translate", "perspective", "clip-path")
            unsafe = (node.kind is NodeKind.NATIVE
                      or any(key in str(props).lower() for key in suspicious)
                      or any(key in str(style).lower() for key in suspicious))
            allowed = clip_safe and not unsafe
            if node.kind is NodeKind.HOST and node.type == "Scroll":
                scroll_ancestor = node
            if node.kind is NodeKind.HOST and node.type == "Grid":
                identifier = path_identity(node.path)
                self.grids[identifier] = node
                self._viewport_allowed[identifier] = allowed
                self._scroll_ancestors[identifier] = scroll_ancestor
                return
            for child in node.effective_children:
                visit(child, allowed, scroll_ancestor)

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
        geometry_reuse = getattr(self, "_geometry_reuse", None)
        accepted = (
            geometry_reuse.lookup(
                node_id, grid, width, self.renderer._sfle_constraints,
                self.generation,
            ) if geometry_reuse is not None else None
        )
        if accepted is not None:
            self._composition_cache[key] = accepted
            return accepted
        # The native baseline is shared by all width probes in this one
        # transaction, including re-entrant nested Grid compositions.
        if self.backend is GridCommitBackend.TK and not getattr(self, "_tk_idle_synced", False):
            self.renderer.root.update_idletasks()
            self._tk_idle_synced = True

        def measure_leaf(identifier, node, allocated_width):
            handle = self.handles[id(node.source)]
            if self.backend is GridCommitBackend.QT:
                from psx.renderers.qt.cinnamon_qt_measurement import QtMeasurementSource
                source = QtMeasurementSource(
                    {identifier: handle.widget}, qtcore=self.renderer._qtcore)
            elif self.backend is GridCommitBackend.TK:
                from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource
                source = TkMeasurementSource(
                    {identifier: handle.widget}, idle_synced=True,
                )
            elif self.backend is GridCommitBackend.KIVY:
                from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource
                # measure_width() already refreshes the native label texture
                # before and after its width-constrained probe. Refreshing
                # here ran *even on accepted GridIntrinsicReuse hits*, so a
                # viewport-only resize needlessly refreshed every text leaf.
                # Let the source refresh only if an actual measurement is due.
                source = KivyMeasurementSource({identifier: handle.widget})
            else:
                raise GridPackingError("Mixed native Grid requires a toolkit backend.")
            reuse_round = getattr(self, "_intrinsic_reuse", None)
            if allocated_width is None:
                if self.backend is not GridCommitBackend.KIVY:
                    raise GridPackingError("Intrinsic unwrapped text width requires Kivy.")
                # This is an explicit native glyph-width probe. Do not reuse
                # a previous width-constrained measurement as its cache key.
                result = source.measure_width(identifier, None)
            else:
                result = (
                reuse_round.measure(
                    self.backend.value, handle.widget, node, allocated_width,
                    lambda: source.measure_width(identifier, allocated_width),
                ) if reuse_round is not None
                else source.measure_width(identifier, allocated_width)
            )
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
            flow_reuse=getattr(self, "_flow_reuse", None),
            invalidation_epoch=getattr(self, "_intrinsic_epoch", 0),
            pixel_scale=(getattr(self.renderer, "_psx_css_pixel_scale", 1.0)
                         if self.backend is GridCommitBackend.KIVY else 1.0),
            kivy_text_basis=(self.backend is GridCommitBackend.KIVY),
        )
        # Never publish a partial result after a measurement exception.
        self._composition_cache[key] = composition
        if geometry_reuse is not None:
            geometry_reuse.stage(
                node_id, grid, width, self.renderer._sfle_constraints, composition,
            )
        return composition

    def accept_intrinsic(self):
        # Call only AFTER the outer renderer's native commit, readback and
        # semantic epoch checks all succeeded. Partial measurements are never
        # published on a rejected/rolled-back transaction.
        reuse_round = getattr(self, "_intrinsic_reuse", None)
        if reuse_round is not None:
            reuse_round.accept(self.renderer._sfle_measurement_invalidations.epoch)

    def accept_solved(self):
        self._flow_reuse.solved.accept(self.generation, self._intrinsic_epoch)
        if self.renderer._sfle_measurement_invalidations.epoch == self._intrinsic_epoch:
            self._geometry_reuse.accept()
        else:
            self._geometry_reuse.discard()

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
            # Convert root-window viewport bottom into Grid-local Y, not
            # the Grid content height. A Grid may extend thousands of px
            # below its visible window without being a Scroll host.
            scroll_ancestor = self._scroll_ancestors.get(node_id)
            if scroll_ancestor is None:
                viewport_height = self.renderer._sfle_constraints.height.value
                self._viewport_tops[node_id] = 0.0
                self._viewport_heights[node_id] = (
                    float(viewport_height) - box.y
                    if viewport_height is not None else 0.0
                )
            else:
                scroll_id = path_identity(scroll_ancestor.path)
                scroll_host = self.handles[id(scroll_ancestor.source)].widget
                if not getattr(scroll_host, "_psx_sfle_scroll", False):
                    self._viewport_allowed[node_id] = False
                scroll_rect = boxes[scroll_id].border
                if self.backend is GridCommitBackend.QT:
                    scroll_y = float(scroll_host.verticalScrollBar().value())
                elif self.backend is GridCommitBackend.TK:
                    scroll_y = float(scroll_host._psx_canvas.canvasy(0))
                else:
                    overflow = getattr(scroll_host, "_psx_scroll_previous_overflow", None)
                    if overflow is None:
                        overflow_y = max(
                            0.0, float(scroll_host._psx_content.height)
                                 - float(scroll_host.height)
                        )
                    else:
                        overflow_y = float(overflow[1])
                    scroll_y = (1.0 - float(scroll_host.scroll_y)) * overflow_y
                self._viewport_tops[node_id] = (
                    scroll_rect.y - box.y + scroll_y
                )
                self._viewport_heights[node_id] = scroll_rect.height
            composition = self.compose(node_id, box.width)
            geometry_reuse = getattr(self, "_geometry_reuse", None)
            cached_batch = (
                geometry_reuse.batch_lookup(
                    node_id, box.width, self.renderer._sfle_constraints,
                    box.height, self.handles,
                ) if geometry_reuse is not None else None
            )
            if cached_batch is not None:
                batch, widgets, heights = cached_batch
            else:
                batch, widgets, heights = compose_geometry_batch(
                    composition,
                    handles={identity: handle.widget
                             for identity, handle in self.handles.items()},
                    root_height=box.height,
                )
                if geometry_reuse is not None:
                    geometry_reuse.batch_stage(
                        node_id, self.grids[node_id], box.width,
                        self.renderer._sfle_constraints, box.height,
                        batch, widgets, heights, self.handles,
                    )
            prepared.append((composition, batch, widgets, heights, box.height))
        return tuple(prepared)

    def viewport_native_widget_ids(self, plans):
        """Preflight sparse Grid work BEFORE the expensive rollback snapshot.

        Every offscreen candidate was physically committed and read back in
        an earlier accepted generation. Structural or semantic invalidation
        disables all skipping; complex CSS and Scroll descendants fail closed.
        """
        cache = getattr(self.renderer, "_psx_mixed_grid_viewport_cache", None)
        if cache is None:
            cache = {}
            self.renderer._psx_mixed_grid_viewport_cache = cache
        planned = []
        active_widget_ids = set()
        epoch = self._intrinsic_epoch
        for node_id, plan in zip(self.grids, plans):
            composition, batch, widgets, heights, root_height = plan
            skipped = frozenset()
            workset = None
            if self._viewport_allowed.get(node_id, False):
                workset = cache.setdefault(node_id, GridViewportWorkset())
                roots = tuple(p.node_id for p in composition.prepared.placements)
                items = {
                    path_identity(item.path): item
                    for item in composition.grid.effective_children
                }
                safe_ids = frozenset(
                    key for key, item in items.items()
                    if subtree_is_safe_for_root_culling(item)
                )
                skipped = workset.plan(
                    root_ids=roots, batch=batch, widgets=widgets,
                    viewport_height=self._viewport_heights.get(node_id, 0.0),
                    epoch=epoch, backend=self.backend, safe_ids=safe_ids,
                    viewport_top=self._viewport_tops.get(node_id, 0.0),
                    reconcile=getattr(self.renderer, '_psx_resize_priority', None),
                )
            else:
                cache.pop(node_id, None)
            planned.append((node_id, workset, skipped))
            active_widget_ids.update(
                id(widget) for key, widget in widgets.items()
                if key not in skipped
            )
        self._viewport_batches = tuple(planned)
        self._viewport_plans = plans
        # Preserve the zero-argument snapshot protocol: native integration
        # and tests wrap snapshot() to audit one rollback capture per commit.
        # Filtering is transaction-local state, not a new required argument.
        self._snapshot_widget_ids = active_widget_ids
        return active_widget_ids

    def accept_viewport(self):
        """Publish offscreen receipts AFTER the outer native transaction."""
        scroll_deferred = {}
        self.renderer._psx_native_grid_deferred_total = sum(
            len(skipped) for _, _, skipped in getattr(self, '_viewport_batches', ())
        )
        for (node_id, workset, skipped), plan in zip(
            getattr(self, "_viewport_batches", ()),
            getattr(self, "_viewport_plans", ()),
        ):
            owner = self._scroll_ancestors.get(node_id)
            if owner is not None:
                host = self.handles[id(owner.source)].widget
                scroll_deferred[id(host)] = (
                    host,
                    bool(skipped) or scroll_deferred.get(id(host), (None, False))[1],
                )
            if workset is None:
                continue
            composition, batch, widgets, _heights, _root_height = plan
            workset.accept(
                root_ids=tuple(p.node_id for p in composition.prepared.placements),
                batch=batch, widgets=widgets,
                viewport_height=self._viewport_heights[node_id],
                epoch=self._intrinsic_epoch, backend=self.backend, skipped=skipped,
            )
        for host, pending in scroll_deferred.values():
            # Grid and HTML flow may share a Scroll viewport. Never let the
            # final acceptance step clear the other layout participant's
            # outstanding deferred native work.
            host._psx_viewport_grid_deferred = pending
            host._psx_viewport_has_deferred = (
                pending or bool(getattr(host, "_psx_viewport_flow_deferred", False))
            )

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

    def snapshot(self, *, only_widget_ids=None):
        """Capture only widgets that the pending transaction may mutate."""
        if only_widget_ids is None:
            only_widget_ids = getattr(self, "_snapshot_widget_ids", None)
        result = []
        for widget in self._descendants():
            if only_widget_ids is not None and id(widget) not in only_widget_ids:
                continue
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
        from psx.layout.adapters.native_scroll_hosts import (
            apply_kivy_scroll, apply_qt_scroll, apply_tk_scroll,
            binding_from_host,
        )
        from psx.layout.runtime.native_scroll_transaction import prior_scroll_offset
        from psx.layout.contracts.model import Rect

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

    def commit(self, plans, *, prior_snapshot=None):
        from psx.layout.runtime.native_scroll_transaction import (
            capture_scroll_hosts, restore_scroll_hosts,
        )
        # The outer SFLE transaction already captured these exact native
        # descendants for rollback. No geometry is mutated between that
        # capture and the nested Grid batch, so do not repeat every native
        # geometry read on the UI thread.
        before = self.snapshot() if prior_snapshot is None else prior_snapshot
        # Scroll hosts referenced by nested Grid compositions can lie
        # outside the geometry rollback descendants. Capture the full
        # mounted handle set for offset restoration until ownership of
        # those hosts can be proven by a dedicated reachability test.
        scroll_before = capture_scroll_hosts(self.backend.value, self.handles)
        receipts = []
        # A single Grid batch has not yet mutated any of its descendants.
        # Its rollback snapshot can also supply the original place_info()
        # state. Multiple batches may overlap (nested Grids), so preserve
        # their own native reads rather than risk using stale rectangles.
        reusable_tk = (
            {id(widget): state for widget, state in before}
            if self.backend is GridCommitBackend.TK and len(plans) == 1
            else None
        )
        reusable_native = (
            {id(widget): state for widget, state in before}
            if self.backend in (GridCommitBackend.QT, GridCommitBackend.KIVY)
               and len(plans) == 1 else None
        )
        try:
            deferred_batches = getattr(self, "_viewport_batches", ())
            for index, (composition, batch, widgets, heights, root_height) in enumerate(plans):
                deferred = (
                    deferred_batches[index][2] if index < len(deferred_batches)
                    else frozenset()
                )
                full_batch = batch
                if deferred:
                    batch = tuple(p for p in batch if p.node_id not in deferred)
                    widgets = {key: widget for key, widget in widgets.items()
                               if key not in deferred}
                    heights = {key: value for key, value in heights.items()
                               if key not in deferred}
                initial_native = None
                if reusable_native is not None and all(
                    id(widget) in reusable_native for widget in widgets.values()
                ):
                    from psx.layout.contracts.model import Rect
                    if self.backend is GridCommitBackend.QT:
                        initial_native = {
                            node_id: Rect(*reusable_native[id(widget)])
                            for node_id, widget in widgets.items()
                        }
                    else:
                        initial_native = {
                            node_id: Rect(
                                *reusable_native[id(widget)][0],
                                *reusable_native[id(widget)][1],
                            )
                            for node_id, widget in widgets.items()
                        }
                initial = (
                    {node_id: reusable_tk[id(widget)]
                     for node_id, widget in widgets.items()
                     if id(widget) in reusable_tk}
                    if reusable_tk is not None else None
                )
                receipt = commit_grid_native_geometry(
                    batch, backend=self.backend, widgets=widgets,
                    prior_tk_placements=initial,
                    prior_native_rectangles=initial_native,
                    generation=self.generation,
                    current_generation=lambda: self.renderer._sfle_generation,
                    is_ui_thread=self._on_thread,
                    parent_height=(root_height
                                   if self.backend is GridCommitBackend.KIVY else None),
                    parent_heights=(heights
                                    if self.backend is GridCommitBackend.KIVY else None),
                    kivy_window_coordinates=(self.backend is GridCommitBackend.KIVY),
                )
                self._bind_nested_scrolls(composition, scroll_before)
                if deferred:
                    receipt = GridNativeCommitReceipt(
                        self.generation, tuple(p.node_id for p in full_batch),
                        receipt.max_readback_error,
                        tuple(p.node_id for p in full_batch if p.node_id in deferred),
                    )
                receipts.append((composition.prepared, receipt))
        except BaseException:
            restore_scroll_hosts(scroll_before)
            self.restore(before)
            raise
        return receipts
