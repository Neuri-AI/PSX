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

from collections import OrderedDict
from dataclasses import replace

from psx.core.vnode import NodeKind
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.layout.adapters.grid_viewport_workset import subtree_is_safe_for_root_culling


_ALLOWED = frozenset(("Grid", "GridItem", "Text", "Flex")) | frozenset(FORMATTING_TAGS)


def _safe_immutable_grid(grid) -> bool:
    """Disallow anything whose intrinsic or paint may change independently."""
    if not subtree_is_safe_for_root_culling(grid):
        return False
    stack = [grid]
    while stack:
        node = stack.pop()
        if node.kind is not NodeKind.HOST or node.type not in _ALLOWED:
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
        self._pending = {}
        self._safety = {}

    def begin(self, normalized, epoch, backend, pixel_scale, breakpoints):
        # The viewport belongs to the *per-entry* key; retaining other exact
        # widths is what makes a continuous back-and-forth resize cheap.
        scope = (epoch, backend, float(pixel_scale), repr(breakpoints))
        if normalized is not self._root or scope != self._scope:
            self._entries.clear()
            self._safety.clear()
            self._root = normalized
            self._scope = scope
        self._pending.clear()

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
        return _rebind_grid(entry, generation)

    def stage(self, grid_id, grid, width, viewport, composition):
        if self.eligible(grid_id, grid):
            self._pending[self._key(grid_id, width, viewport)] = composition

    def accept(self):
        # Never publish a speculative measurement on a failed UI transaction.
        for key, composition in self._pending.items():
            self._entries[key] = composition
            self._entries.move_to_end(key)
        while len(self._entries) > self.limit:
            self._entries.popitem(last=False)
        self._pending.clear()

    def discard(self):
        self._pending.clear()
