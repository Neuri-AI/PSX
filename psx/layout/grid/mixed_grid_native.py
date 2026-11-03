"""Width-dependent Grid participants inside mounted Flex/Scroll trees.

Cinnamon Flex assigns a Grid content width; Cinnamon Grid independently
measures and places its descendants. Toolkits do not calculate sibling layout.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
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


class _WidgetBindings(Mapping):
    """Resolve only widgets referenced by the transaction's native batch."""
    def __init__(self, handles):
        self.handles = handles
        self.sources = {}
        self.ambiguous = False

    def __getitem__(self, key):
        from psx.core.structural_binding import widget_identity
        widget = self.handles[key].widget
        identity = widget_identity(widget)
        previous = self.sources.get(identity)
        if previous is not None and previous != key:
            self.ambiguous = True
        self.sources[identity] = key
        return widget

    def __iter__(self):
        return iter(self.handles)

    def __len__(self):
        return len(self.handles)


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
        self._native_materialization_plans = ()
        self._omitted_roots = {}
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
        self._normalized = normalized
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
        pending_uniform = None
        accepted = (
            geometry_reuse.lookup(
                node_id, grid, width, self.renderer._sfle_constraints,
                self.generation,
            ) if geometry_reuse is not None else None
        )
        if accepted is not None:
            self._composition_cache[key] = accepted
            return accepted
        if (geometry_reuse is not None
                and getattr(self.renderer, "_psx_in_native_viewport_resize", False)):
            viewport_receipt = geometry_reuse.lookup_viewport(
                node_id, width, self.renderer._sfle_constraints, self.generation)
            if viewport_receipt is not None:
                self._composition_cache[key] = viewport_receipt
                return viewport_receipt
            owner = getattr(self.renderer, "_psx_reconciler", None)
            if owner is not None:
                from psx.layout.grid.grid_uniform_projection import prepare_uniform_grid
                proof = geometry_reuse.uniform_proof(node_id, self._normalized, grid)
                pixel_scale = (getattr(self.renderer, "_psx_css_pixel_scale", 1.0)
                               if self.backend is GridCommitBackend.KIVY else 1.0)
                compressed = prepare_uniform_grid(
                    proof,
                    width=width, viewport=self.renderer._sfle_constraints,
                    generation=self.generation, engine=self.renderer._sfle_engine,
                    native_instances=owner._native_instances.values(),
                    report_fallback=lambda reason: geometry_reuse.structural_fallbacks.update((reason,)),
                    allow_dirty_tail=True,
                    pixel_scale=pixel_scale)
                if compressed is not None:
                    self._composition_cache[key] = compressed
                    if compressed.provisional_ids:
                        geometry_reuse.early_provisional_groups += len(compressed.provisional_ids)
                        geometry_reuse.stage_viewport(node_id, grid, width,
                                                     self.renderer._sfle_constraints, compressed)
                    else:
                        geometry_reuse.exact_unwrapped_groups += len(compressed.prepared.child_ids)
                        geometry_reuse.stage(node_id, grid, width,
                                             self.renderer._sfle_constraints, compressed)
                    return compressed
                if (proof is not None and pixel_scale == 1.0
                        and (width - (proof.per_row - 1) * proof.column_gap)
                            / proof.per_row - 1 / 64 < proof.threshold):
                    pending_uniform = proof
        deferred_flows = {}
        reusable_flows = {}
        if (geometry_reuse is not None
                and pending_uniform is None
                and getattr(self.renderer, "_psx_in_native_viewport_resize", False)):
            # This runs *before* constructing native measurement callbacks,
            # scanning a Flow's children or invoking Cinnamon on its subtree.
            # Only previously accepted groups with proven non-visible future
            # bounds are eligible; a non-resize, idle or scroll commit always
            # takes the normal exact path.
            from psx.layout.grid.grid_early_viewport import (
                select_pre_measurement_deferred_flows,
            )
            worksets = getattr(
                self.renderer, "_psx_mixed_grid_viewport_cache", None,
            ) or {}
            structural_plan = geometry_reuse.early_plan(
                node_id, self._normalized, grid,
            )
            if structural_plan is not None:
                deferred_flows = select_pre_measurement_deferred_flows(
                    self._normalized, grid,
                    geometry_reuse.latest(node_id), worksets.get(node_id),
                    viewport_height=self.renderer._sfle_constraints.height.value,
                    epoch=self._intrinsic_epoch, static_plan=structural_plan,
                    content_width=width,
                )
            # A wider normal-flow card whose text was already proven not to
            # wrap has identical intrinsic height.  Reuse it for *all* rows,
            # including P0/P1, so Grid can produce and retain an exact
            # current-width receipt instead of a provisional P2-only one.
            from psx.layout.grid.grid_early_viewport import (
                select_wider_unwrapped_flows,
            )
            reusable_flows = select_wider_unwrapped_flows(
                grid, geometry_reuse.latest(node_id), content_width=width,
                static_plan=structural_plan,
            )
            if len(reusable_flows) == len(grid.effective_children):
                geometry_reuse.exact_unwrapped_groups += len(reusable_flows)
                # The new Grid solve is fully current-width exact; P2 no
                # longer needs an older-flow placeholder and may be cached.
        # The native baseline is shared by all width probes in this one
        # transaction, including re-entrant nested Grid compositions.
        if self.backend is GridCommitBackend.TK and not getattr(self, "_tk_idle_synced", False):
            self.renderer.root.update_idletasks()
            self._tk_idle_synced = True

        def measure_leaf(identifier, node, allocated_width):
            from psx.layout.runtime.structural_text_probe import measure_without_native_handle
            intrinsic = measure_without_native_handle(
                self.renderer, node, self.handles, allocated_width, self.backend.value)
            if intrinsic is not None:
                reuse_round = getattr(self, "_intrinsic_reuse", None)
                if reuse_round is not None and allocated_width is not None:
                    return reuse_round.measure(
                        self.backend.value, self.handles[id(node.source)].widget,
                        node, allocated_width, lambda: intrinsic,
                    )
                return intrinsic
            from psx.core.structural_binding import materialize_for_measurement
            materialize_for_measurement(self.renderer, node, self.handles)
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
                # This is an explicit native glyph-width probe. Do not reuse
                # a previous width-constrained measurement as its cache key.
                if self.backend is GridCommitBackend.KIVY:
                    result = source.measure_width(identifier, None)
                else:
                    from psx.layout.runtime.measurement_plan import MeasurementRequest
                    if self.backend is GridCommitBackend.QT and node.type == "Text":
                        source._text_ids = frozenset({identifier})
                    result = source.measure(MeasurementRequest(identifier, LayoutConstraints(
                        AvailableSize(None, False), AvailableSize(None, False)), 0, 0)).intrinsic
                    if self.backend is GridCommitBackend.QT and node.type == "Text":
                        natural_width = result.preferred_width + 1.0
                        result = source.measure_width(identifier, natural_width)
                        result = replace(result, preferred_width=natural_width,
                                         max_content_width=max(result.max_content_width, natural_width))
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

        # Native constrained hints can clamp the preferred width to the probe
        # even when text wrapped. A separate real unwrapped probe certifies
        # both natural glyph width and unchanged line height before reuse.
        measure_leaf.unwrapped = lambda identifier, node: measure_leaf(identifier, node, None)
        if pending_uniform is not None:
            from psx.layout.grid.grid_uniform_projection import prepare_deferred_grid_window

            def compose_prefix(prefix):
                allocated = ((width - (pending_uniform.per_row - 1)
                              * pending_uniform.column_gap)
                             / pending_uniform.per_row - 1 / 64)
                reusable = {}
                for item in prefix.children:
                    identifier = pending_uniform.source_ids[id(item.source)]
                    flow = pending_uniform.base.nested_flow[identifier]
                    if flow.unwrapped_at_width <= allocated:
                        reusable[identifier] = flow
                return prepare_composed_grid(prefix, content_width=width,
                    generation=self.generation, current_generation=self.renderer._sfle_generation,
                    measure_leaf=measure_leaf, is_ui_thread=self._on_thread,
                    breakpoints=self.breakpoints, engine=self.renderer._sfle_engine,
                    viewport_constraints=self.renderer._sfle_constraints,
                    flow_reuse=self._flow_reuse, invalidation_epoch=self._intrinsic_epoch,
                    reusable_flows=reusable,
                    kivy_text_basis=(self.backend is GridCommitBackend.KIVY))

            composition = prepare_deferred_grid_window(pending_uniform,
                width=width, viewport=self.renderer._sfle_constraints,
                generation=self.generation, engine=self.renderer._sfle_engine,
                native_instances=owner._native_instances.values(), compose_prefix=compose_prefix)
            if composition is not None:
                self._composition_cache[key] = composition
                geometry_reuse.early_provisional_groups += len(composition.provisional_ids)
                geometry_reuse.stage_viewport(node_id, grid, width,
                                             self.renderer._sfle_constraints, composition)
                return composition
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
            deferred_flows=deferred_flows,
            reusable_flows=reusable_flows,
        )
        if deferred_flows and geometry_reuse is not None:
            geometry_reuse.early_provisional_groups += len(
                composition.provisional_ids)
        # Never publish a partial result after a measurement exception.
        self._composition_cache[key] = composition
        if geometry_reuse is not None and not composition.provisional_ids:
            geometry_reuse.stage(
                node_id, grid, width, self.renderer._sfle_constraints, composition,
            )
        elif geometry_reuse is not None:
            geometry_reuse.stage_viewport(
                node_id, grid, width, self.renderer._sfle_constraints, composition)
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
            omitted = frozenset()
            items = None
            structural_only = composition.provisional_ids | composition.native_deferred_flows
            plain_plan = (geometry_reuse.early_plan(node_id, self._normalized, composition.grid)
                          if geometry_reuse is not None else None)
            if plain_plan is not None and plain_plan[3]:
                # These tail groups were proven P2 before composition. Their
                # structural receipts remain in Cinnamon; an absent native
                # subtree has nothing to validate, commit, retire or read back.
                items = geometry_reuse.item_nodes(node_id, composition.grid)
                workset = (getattr(self.renderer, "_psx_mixed_grid_viewport_cache", {})
                           .get(node_id))
                owner = getattr(self.renderer, "_psx_reconciler", None)
                if composition.viewport_roots is not None:
                    omitted = structural_only
                elif owner is not None:
                    omitted = geometry_reuse.omitted_native_roots(
                        node_id, composition, self.handles, workset,
                        viewport_top=self._viewport_tops[node_id],
                        viewport_height=self._viewport_heights[node_id],
                        epoch=self._intrinsic_epoch, native_revision=owner._native_revision)
            self._omitted_roots[node_id] = omitted
            cached_batch = (
                geometry_reuse.batch_lookup(
                    node_id, box.width, self.renderer._sfle_constraints,
                    box.height, self.handles,
                    omitted_roots=omitted,
                ) if geometry_reuse is not None else None
            )
            if cached_batch is not None:
                batch, widgets, heights = cached_batch
            else:
                native_bindings = _WidgetBindings(self.handles)
                batch, widgets, heights = compose_geometry_batch(
                    composition,
                    handles=native_bindings,
                    root_height=box.height,
                    omitted_roots=omitted, root_items=items,
                )
                if (geometry_reuse is not None
                        and (not composition.provisional_ids or omitted == structural_only)
                        and not native_bindings.ambiguous):
                    geometry_reuse.batch_stage(
                        node_id, self.grids[node_id], box.width,
                        self.renderer._sfle_constraints, box.height,
                        batch, widgets, heights, self.handles,
                        omitted_roots=omitted,
                        binding_sources=native_bindings.sources,
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
        materialization = []
        active_widget_ids = set()
        active_widgets = {}
        epoch = self._intrinsic_epoch
        for node_id, plan in zip(self.grids, plans):
            composition, batch, widgets, heights, root_height = plan
            skipped = frozenset()
            workset = None
            if self._viewport_allowed.get(node_id, False):
                workset = cache.setdefault(node_id, GridViewportWorkset())
                omitted = self._omitted_roots.get(node_id, frozenset())
                safe_ids = self._geometry_reuse.viewport_safe_items(
                    node_id, composition.grid,
                )
                roots = (composition.viewport_roots
                         if composition.viewport_roots is not None else tuple(
                             p.node_id for p in batch if p.node_id in safe_ids))
                skipped = workset.plan(
                    root_ids=roots, batch=batch, widgets=widgets,
                    viewport_height=self._viewport_heights.get(node_id, 0.0),
                    epoch=epoch, backend=self.backend, safe_ids=safe_ids,
                    viewport_top=self._viewport_tops.get(node_id, 0.0),
                    reconcile=getattr(self.renderer, '_psx_resize_priority', None),
                )
                # The MixedGrid route is used by ordinary card grids nested
                # in Flex/Block roots.  Attach P0/P1 item roots before the
                # outer commit, then defer physical detachment until that
                # commit has been accepted in ``accept_viewport``.
                from psx.layout.adapters.native_flow_viewport import FlowViewportPlan
                from psx.core.native_materialization import synchronize_native_materialization
                materialization_plan = FlowViewportPlan(
                    workset, roots, tuple(batch), dict(widgets),
                    float(self._viewport_heights.get(node_id, 0.0)),
                    epoch, self.backend.value, frozenset(skipped),
                    float(self._viewport_tops.get(node_id, 0.0)),
                    release_native=True,
                    retained_roots=omitted,
                )
                root = getattr(self.renderer, "_sfle_mounted_root", None)
                if root is None:
                    root = getattr(getattr(self.renderer, "_psx_reconciler", None), "root", None)
                if root is not None:
                    materialization_plan = synchronize_native_materialization(
                        self.renderer, root, widgets, materialization_plan,
                    )
                    skipped = materialization_plan.deferred_ids
                materialization.append(materialization_plan)
            else:
                cache.pop(node_id, None)
                materialization.append(None)
            # A provisional Flow has prior-width child rectangles. It must
            # NEVER reach a native setter: do not silently treat its old
            # geometry as a full current-width solved result. Refuse the
            # transaction before any native widget mutation if the P2 proof
            # was invalidated between measuring and viewport classification.
            provisional = ((composition.provisional_ids | composition.native_deferred_flows)
                           - self._omitted_roots.get(node_id, frozenset()))
            if provisional:
                groups = GridViewportWorkset._groups(roots, batch, widgets)
                for group_id in provisional:
                    if (group_id not in groups
                            or not all(
                                placement.node_id in skipped
                                for placement in groups[group_id]
                            )):
                        raise GridPackingError(
                            "Provisional offscreen Grid Flow became visible "
                            "before a fully measured layout."
                        )
            planned.append((node_id, workset, skipped))
            active_widget_ids.update(
                id(widget) for key, widget in widgets.items()
                if key not in skipped
            )
            active_widgets.update({id(widget): widget for key, widget in widgets.items()
                                   if key not in skipped})
        self._viewport_batches = tuple(planned)
        self._native_materialization_plans = tuple(materialization)
        self._viewport_plans = plans
        # Preserve the zero-argument snapshot protocol: native integration
        # and tests wrap snapshot() to audit one rollback capture per commit.
        # Filtering is transaction-local state, not a new required argument.
        self._snapshot_widget_ids = active_widget_ids
        self._snapshot_widgets = tuple(active_widgets.values())
        return active_widget_ids

    def accept_viewport(self):
        """Publish offscreen receipts AFTER the outer native transaction."""
        scroll_deferred = {}
        self.renderer._psx_native_grid_deferred_total = sum(
            len(skipped) for _, _, skipped in getattr(self, '_viewport_batches', ())
        ) + sum(len(roots) for roots in self._omitted_roots.values())
        for index, ((node_id, workset, skipped), plan) in enumerate(zip(
            getattr(self, "_viewport_batches", ()),
            getattr(self, "_viewport_plans", ()),
        )):
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
            materialization = getattr(self, "_native_materialization_plans", ())
            materialization_plan = (materialization[index]
                                    if index < len(materialization) else None)
            if materialization_plan is not None:
                from psx.core.native_materialization import finalize_native_materialization
                root = getattr(self.renderer, "_sfle_mounted_root", None)
                if root is None:
                    root = getattr(getattr(self.renderer, "_psx_reconciler", None), "root", None)
                if root is not None:
                    materialization_plan = finalize_native_materialization(
                        self.renderer, root, widgets, materialization_plan,
                    )
                    skipped = materialization_plan.deferred_ids
                materialization_plan.accept()
            else:
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
        candidates = getattr(self, "_snapshot_widgets", None)
        for widget in (candidates if candidates is not None else self._descendants()):
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
        certified_plain_grid = (len(self.grids) == 1 and self._geometry_reuse.early_plan(
            next(iter(self.grids)), self._normalized, next(iter(self.grids.values()))) is not None)
        scroll_before = (() if certified_plain_grid
                         else capture_scroll_hosts(self.backend.value, self.handles))
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
                if not certified_plain_grid:
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
