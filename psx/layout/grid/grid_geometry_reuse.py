"""Commit-accepted exact geometry reuse *before* Grid intrinsic measurement.

A mixed native Grid is usually asked to solve the same responsive widths many
times during a resize gesture.  Solved text-subtree reuse alone still walks
every card, constructs native measurement requests, calls Grid and flattens
every resulting rectangle.  This cache skips all of that on a certified exact
viewport/width hit, before any of those steps begin.

Only immutable, ordinary Grid/Text/HTML/Flex subtrees are eligible. No native
handles, active controls, Scroll hosts or uncertain CSS positioning are
cached. Every acceptance follows a successful native commit/readback.
"""
from __future__ import annotations

from collections import OrderedDict, Counter
from dataclasses import replace

from psx.core.vnode import NodeKind
from psx.core.structural_binding import widget_identity
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.layout.adapters.grid_viewport_workset import subtree_is_safe_for_root_culling


# Form labels can respond to focus/semantic state without replacing their
# authored VNode; fail closed instead of memoizing interactive native paint.
_ALLOWED = (frozenset(("Grid", "GridItem", "Text", "Flex"))
            | (frozenset(FORMATTING_TAGS) - {"form", "label"}))


def _safe_immutable_grid(grid) -> bool:
    """Disallow anything whose intrinsic or paint may change independently."""
    if not subtree_is_safe_for_root_culling(grid):
        return False
    stack = [grid]
    while stack:
        node = stack.pop()
        if node.kind is not NodeKind.HOST or node.type not in _ALLOWED:
            return False
        props = getattr(node.source, "props", {}) or {}
        # External refs/handlers can mutate native text or size independently
        # of a committed immutable VNode. Such a subtree is not eligible for
        # cross-generation geometry reuse or provisional P2 measurements.
        if ("ref" in props or any(
            str(name).startswith("on_") or callable(value)
            for name, value in props.items()
        )):
            return False
        stack.extend(node.effective_children)
    return True


def _rebind_flow(flow, generation):
    prepared = replace(
        flow.prepared,
        snapshot=replace(flow.prepared.snapshot, generation=generation),
    )
    return replace(
        flow, prepared=prepared,
        result=replace(flow.result, generation=generation,
                       geometry_commit_error=None),
        nested_grids={key: _rebind_grid(child, generation)
                      for key, child in flow.nested_grids.items()},
    )


def _rebind_flex(flex, generation):
    prepared = replace(
        flex.prepared,
        snapshot=replace(flex.prepared.snapshot, generation=generation),
    )
    return replace(
        flex, prepared=prepared,
        result=replace(flex.result, generation=generation,
                       geometry_commit_error=None),
        nested_grids={key: _rebind_grid(child, generation)
                      for key, child in flex.nested_grids.items()},
    )


def _rebind_grid(grid, generation):
    prepared = replace(
        grid.prepared, generation=generation,
        measurement_revisions=tuple(
            (node_id, generation) for node_id in grid.prepared.child_ids
        ),
    )
    return replace(
        grid, prepared=prepared,
        nested={key: _rebind_grid(child, generation)
                for key, child in grid.nested.items()},
        nested_flow={key: _rebind_flow(child, generation)
                     for key, child in grid.nested_flow.items()},
        nested_flex={key: _rebind_flex(child, generation)
                     for key, child in grid.nested_flex.items()},
        nested_scroll={
            key: (_rebind_flow(part[0], generation), *part[1:])
            for key, part in grid.nested_scroll.items()
        },
    )


class AcceptedGridGeometryReuse:
    """UI-thread-only bounded memo for *exact* previously accepted layouts.

    The structural projection is already guarded by the mounted-instance
    signature, including widget handles and immutable CSS snapshots. Holding
    the normalized tree prevents id() recycling. Any structural edit,
    semantic measurement invalidation or backend change drops all receipts.
    """

    def __init__(self, limit: int = 16):
        if limit < 1:
            raise ValueError("A positive geometry cache bound is required")
        self.limit = limit
        self.hits = 0
        self.misses = 0
        self._root = None
        self._scope = None
        self._entries = OrderedDict()
        self._viewport_entries = OrderedDict()
        self._viewport_pending = {}
        self._pending = {}
        self._safety = {}
        self._viewport_safe_items = {}
        self._early_plans = {}
        self._item_nodes = {}
        self._native_omissions = OrderedDict()
        self._uniform_proofs = {}
        self._batch_entries = OrderedDict()
        self._batch_pending = {}
        self._latest = OrderedDict()
        self.batch_hits = 0
        self.early_provisional_groups = 0
        self.exact_unwrapped_groups = 0
        self.structural_fallbacks = Counter()

    def clear(self):
        """Release all retained VNodes/geometry after unmount or renderer close."""
        self._root = None
        self._scope = None
        self._entries.clear()
        self._viewport_entries.clear()
        self._viewport_pending.clear()
        self._pending.clear()
        self._safety.clear()
        self._viewport_safe_items.clear()
        self._early_plans.clear()
        self._item_nodes.clear()
        self._native_omissions.clear()
        self._uniform_proofs.clear()
        self._batch_entries.clear()
        self._batch_pending.clear()
        self._latest.clear()

    def begin(self, normalized, epoch, backend, pixel_scale, breakpoints):
        # The viewport belongs to the *per-entry* key; retaining other exact
        # widths is what makes a continuous back-and-forth resize cheap.
        scope = (epoch, backend, float(pixel_scale), repr(breakpoints))
        if normalized is not self._root or scope != self._scope:
            self._entries.clear()
            self._viewport_entries.clear()
            self._safety.clear()
            self._viewport_safe_items.clear()
            self._early_plans.clear()
            self._item_nodes.clear()
            self._native_omissions.clear()
            self._uniform_proofs.clear()
            self._batch_entries.clear()
            self._latest.clear()
            self._root = normalized
            self._scope = scope
        self._pending.clear()
        self._viewport_pending.clear()
        self._batch_pending.clear()

    def _key(self, grid_id, width, viewport):
        return (grid_id, float(width),
                float(viewport.width.value), float(viewport.height.value),
                viewport.width.definite, viewport.height.definite)

    def eligible(self, grid_id, grid):
        cached = self._safety.get(grid_id)
        if cached is None:
            cached = _safe_immutable_grid(grid)
            self._safety[grid_id] = cached
        return cached

    def viewport_safe_items(self, grid_id, grid):
        """Cache per-GridItem culling certificates for an immutable tree."""
        cached = self._viewport_safe_items.get(grid_id)
        if cached is None:
            from psx.layout.projection.native_layout_snapshot import path_identity
            cached = frozenset(
                path_identity(item.path) for item in grid.effective_children
                if subtree_is_safe_for_root_culling(item)
            )
            self._viewport_safe_items[grid_id] = cached
        return cached

    def lookup(self, grid_id, grid, width, viewport, generation):
        if not self.eligible(grid_id, grid):
            return None
        key = self._key(grid_id, width, viewport)
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        # This is an accepted, exact immutable receipt.  The caller's native
        # transaction has its own current-generation fence; rebuilding every
        # nested ``ComposedFlow`` merely to stamp that generation used to
        # allocate thousands of Rect/LayoutResult dataclasses on a cache hit.
        # Keep the cached geometry opaque and let newly measured/provisional
        # paths continue to create generation-specific receipts.
        return replace(entry, prepared=replace(
            entry.prepared, generation=generation,
            measurement_revisions=tuple(
                (node_id, generation) for node_id in entry.prepared.child_ids
            ),
        ))

    def stage(self, grid_id, grid, width, viewport, composition):
        # A provisional composition contains old offscreen intrinsic values.
        # It must never become the source of a future accepted exact result.
        if (self.eligible(grid_id, grid)
                and not getattr(composition, "provisional_ids", frozenset())):
            self._pending[self._key(grid_id, width, viewport)] = composition

    def lookup_viewport(self, grid_id, width, viewport, generation):
        """Replay P0/P1 of a certified plain-window Grid, retaining P2 dirty.

        This is deliberately distinct from an exact structural cache hit.
        P2 heights/descendant rectangles remain marked provisional. A clip or
        viewport change misses, and callers must still prove those groups
        absent before native acceptance. Scroll-dependent extents are never
        eligible for this receipt.
        """
        key = self._key(grid_id, width, viewport)
        entry = self._viewport_entries.get(key)
        if entry is None:
            return None
        self._viewport_entries.move_to_end(key)
        self.hits += 1
        return replace(entry, prepared=replace(entry.prepared, generation=generation))

    def stage_viewport(self, grid_id, grid, width, viewport, composition):
        if (composition.provisional_ids and self.eligible(grid_id, grid)
                and self._early_plans.get(grid_id) is not None):
            self._viewport_pending[self._key(grid_id, width, viewport)] = composition

    def latest(self, grid_id):
        """Most recent *fully solved*, committed composition for this Grid."""
        return self._latest.get(grid_id)

    def item_nodes(self, grid_id, grid):
        cached = self._item_nodes.get(grid_id)
        if cached is None:
            from psx.layout.projection.native_layout_snapshot import path_identity
            cached = {path_identity(item.path): item for item in grid.effective_children}
            self._item_nodes[grid_id] = cached
        return cached

    def uniform_proof(self, grid_id, normalized, grid):
        if grid_id not in self._uniform_proofs:
            from psx.layout.grid.grid_uniform_projection import certify_uniform_flows
            self._uniform_proofs[grid_id] = certify_uniform_flows(
                self.latest(grid_id), self.early_plan(grid_id, normalized, grid))
        return self._uniform_proofs[grid_id]

    def omitted_native_roots(self, grid_id, composition, handles, workset, *,
                             viewport_top, viewport_height, epoch, native_revision):
        """Index absent P2 once for each immutable geometry/native incarnation.

        Only normal-flow, non-scrolling root Grids reach this method. Positive
        descendant coordinates and a root below the overscan boundary prove
        the entire group absent independently of native readback.
        """
        placements = composition.prepared.placements
        key = (grid_id, id(placements), viewport_top, viewport_height, native_revision)
        cached = self._native_omissions.get(key)
        if cached is not None and cached[0] is placements:
            self._native_omissions.move_to_end(key)
            return cached[1]
        items = self.item_nodes(grid_id, composition.grid)
        receipts = getattr(workset, "_accepted", {})
        cutoff = viewport_top + viewport_height + 96.0
        omitted = frozenset(p.node_id for p in placements
            if p.y >= cutoff
            and getattr(getattr(handles[id(items[p.node_id].source)], "instance", None),
                        "native_suspended", False)
            and p.node_id in receipts and receipts[p.node_id].epoch == epoch)
        self._native_omissions[key] = (placements, omitted)
        while len(self._native_omissions) > self.limit:
            self._native_omissions.popitem(last=False)
        return omitted

    def early_plan(self, grid_id, normalized, grid):
        """Run expensive CSS and row proofs only once per mounted tree."""
        if grid_id not in self._early_plans:
            from psx.layout.grid.grid_early_viewport import build_early_viewport_plan
            self._early_plans[grid_id] = (
                build_early_viewport_plan(normalized, grid)
                if self.eligible(grid_id, grid) else None
            )
        return self._early_plans[grid_id]

    def accept(self):
        # Never publish a speculative measurement on a failed UI transaction.
        for key, composition in self._viewport_pending.items():
            self._viewport_entries[key] = composition
            self._viewport_entries.move_to_end(key)
        while len(self._viewport_entries) > self.limit:
            self._viewport_entries.popitem(last=False)
        self._viewport_pending.clear()
        for key, composition in self._pending.items():
            self._entries[key] = composition
            self._entries.move_to_end(key)
            self._latest[key[0]] = composition
            self._latest.move_to_end(key[0])
        while len(self._latest) > self.limit:
            self._latest.popitem(last=False)
        while len(self._entries) > self.limit:
            self._entries.popitem(last=False)
        self._pending.clear()
        for key, batch in self._batch_pending.items():
            self._batch_entries[key] = batch
            self._batch_entries.move_to_end(key)
        while len(self._batch_entries) > self.limit:
            self._batch_entries.popitem(last=False)
        self._batch_pending.clear()

    def batch_lookup(self, grid_id, width, viewport, root_height, handles,
                     *, omitted_roots=frozenset()):
        """Replay flattened immutable rectangles; bind *current* UI widgets.

        No native widget is retained between transactions. The original
        widget identity is verified against the live mounted handle before
        returning a cached batch. A mismatched handle safely misses.
        """
        key = (*self._key(grid_id, width, viewport), float(root_height), omitted_roots)
        cached = self._batch_entries.get(key)
        if cached is None:
            return None
        placements, bindings, heights = cached
        widgets = {}
        for placement_id, source_id, expected_widget_id in bindings:
            handle = handles.get(source_id)
            if (handle is None
                    or widget_identity(getattr(handle, "widget", None)) != expected_widget_id):
                self._batch_entries.pop(key, None)
                return None
            widgets[placement_id] = handle.widget
        self._batch_entries.move_to_end(key)
        self.batch_hits += 1
        return placements, widgets, heights

    def batch_stage(self, grid_id, grid, width, viewport, root_height,
                    placements, widgets, heights, handles, *, omitted_roots=frozenset(),
                    binding_sources=None):
        """Stage placement geometry only; never stage native handles."""
        if not self.eligible(grid_id, grid):
            return
        native_to_source = (binding_sources if binding_sources is not None else {
            widget_identity(handle.widget): source_id for source_id, handle in handles.items()
        })
        if binding_sources is None and len(native_to_source) != len(handles):
            # Multiple normalized sources sharing one native widget cannot
            # produce an unambiguous identity receipt.
            return
        bindings = []
        for placement_id, widget in widgets.items():
            source_id = native_to_source.get(widget_identity(widget))
            if source_id is None:
                return
            bindings.append((placement_id, source_id, widget_identity(widget)))
        key = (*self._key(grid_id, width, viewport), float(root_height), omitted_roots)
        self._batch_pending[key] = (
            tuple(placements), tuple(bindings),
            None if heights is None else dict(heights),
        )

    def discard(self):
        self._pending.clear()
        self._viewport_pending.clear()
        self._batch_pending.clear()
