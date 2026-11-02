"""Automatic sparse native geometry worksets for ordinary Flex/HTML flows.

Select repeated sibling subtrees from the *already solved* immutable Cinnamon
snapshot. The workset never guesses sizes or scroll extents. The first commit
is complete. Subsequent viewport resizes can defer ordinary offscreen native
setters/readback for groups with unchanged accepted identity and stable CSS.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from types import SimpleNamespace

from psx.core.vnode import NodeKind
from psx.layout.adapters.grid_viewport_workset import (
    GridViewportWorkset, subtree_is_safe_for_root_culling,
)
from psx.layout.grid.grid_native_plan import GridNativePlacement


@dataclass(frozen=True, slots=True)
class FlowViewportPlan:
    workset: GridViewportWorkset | None
    roots: tuple[str, ...]
    placements: tuple[GridNativePlacement, ...]
    widgets: dict[str, object]
    height: float
    epoch: int
    backend: str
    deferred_ids: frozenset[str]
    viewport_top: float = 0.0
    scroll_host: object | None = None

    def accept(self) -> None:
        if self.workset is not None:
            self.workset.accept(
                root_ids=self.roots, batch=self.placements,
                widgets=self.widgets, viewport_height=self.height,
                epoch=self.epoch, backend=self.backend, skipped=self.deferred_ids,
                viewport_top=self.viewport_top,
            )
        if self.scroll_host is not None:
            # Already mounted Qt, Kivy and Tk Scroll hosts observe their
            # own input; a newly visible subtree requests one coalesced
            # owner-thread Cinnamon transaction, never a second geometry
            # solver or a widget remount.
            self.scroll_host._psx_viewport_has_deferred = bool(self.deferred_ids)


def plan_native_flow_viewport(renderer, prepared, snapshot, result, bindings,
                              backend: str, epoch: int) -> FlowViewportPlan:
    """Choose the widest repeated sibling tier, fail closed on CSS/Scroll.

    Each group is a complete subtree including all descendants. A dense list
    of card subtrees is eligible regardless of whether its parent is Flex,
    Grid-less CSS Block, or an HTML-like div. We never skip an isolated widget,
    nested Grid ownership, a native control or an ancestor Scroll viewport.
    """
    height_axis = getattr(getattr(renderer, "_sfle_constraints", None), "height", None)
    height = getattr(height_axis, "value", None)
    empty = FlowViewportPlan(None, (), (), {}, 0.0, epoch, backend, frozenset())
    if (height is None or not isinstance(height, (float, int))
            or not isfinite(height) or height <= 0):
        return empty
    nodes = tuple(snapshot.nodes)
    if not nodes or not result.boxes:
        return empty
    parents = {node.node_id: node.parent_id for node in nodes}
    by_id = {node.node_id: node for node in nodes}
    children = defaultdict(list)
    for node in nodes[1:]:
        children[node.parent_id].append(node.node_id)
    # Only a dense sibling tier merits grouping. Do not approximate layout
    # beyond this already solved snapshot. One selected parent means groups
    # can never overlap or invalidate each other by double-inclusion.
    candidates = sorted(
        (ids for ids in children.values() if len(ids) >= 12),
        key=len, reverse=True,
    )
    if not candidates:
        return empty
    identity = dict(prepared.identities)
    group_roots = None
    scroll_owner = None
    for proposed in candidates:
        current = parents[proposed[0]]
        unsafe_owner = False
        owner_id = None
        while current is not None:
            source = identity.get(current)
            if source is None or source.kind is NodeKind.NATIVE or source.type == "Grid":
                unsafe_owner = True
                break
            if source.type == "Scroll":
                # A single scroll owner can clip the whole repeated list.
                # Nested scroll transforms have their own coordinate spaces,
                # so they are not eligible for this simple workset.
                if owner_id is not None:
                    unsafe_owner = True
                    break
                owner_id = current
            else:
                # CSS positioning/transform outside a clip can paint into
                # the viewport even when all descendants are below it.
                proxy = SimpleNamespace(
                    kind=source.kind, type=source.type, source=source,
                    effective_children=(),
                )
                if not subtree_is_safe_for_root_culling(proxy):
                    unsafe_owner = True
                    break
            current = parents.get(current)
        if not unsafe_owner:
            group_roots = tuple(proposed)
            scroll_owner = owner_id
            break
    if group_roots is None:
        return empty

    boxes = dict(result.boxes)
    viewport_top = 0.0
    scroll_host = None
    if scroll_owner is not None:
        scroll_host = getattr(bindings[scroll_owner], "widget", bindings[scroll_owner])
        if not getattr(scroll_host, "_psx_sfle_scroll", False):
            return empty
        viewport_rect = boxes[scroll_owner].border
        height = viewport_rect.height
        if backend == "qt":
            scroll_y = float(scroll_host.verticalScrollBar().value())
        elif backend == "tk":
            scroll_y = float(scroll_host._psx_canvas.canvasy(0))
        else:
            overflow = getattr(scroll_host, "_psx_scroll_previous_overflow", None)
            extent_y = (float(overflow[1]) if overflow is not None
                        else max(0.0, float(scroll_host._psx_content.height)
                                 - float(scroll_host.height)))
            scroll_y = (1.0 - float(scroll_host.scroll_y)) * extent_y
        viewport_top = viewport_rect.y + scroll_y
    grouped = []
    safe_ids = set()
    widgets = {}
    for root_id in group_roots:
        stack = [root_id]
        group = []
        safe = True
        while stack:
            current = stack.pop()
            group.append(current)
            stack.extend(reversed(children.get(current, ())))
        for index, key in enumerate(group):
            source = identity.get(key)
            if source is None or key not in bindings:
                return empty
            proxy = SimpleNamespace(
                kind=source.kind, type=source.type, source=source,
                effective_children=(),
            )
            if not subtree_is_safe_for_root_culling(proxy):
                safe = False
            rect = boxes[key].border
            if index == 0:
                pos_x, pos_y = rect.x, rect.y
            else:
                parent = boxes[parents[key]].border
                pos_x, pos_y = rect.x - parent.x, rect.y - parent.y
            grouped.append(GridNativePlacement(
                key, pos_x, pos_y, rect.width, rect.height,
                rect.width, rect.height, False, False,
            ))
            widgets[key] = getattr(bindings[key], "widget", bindings[key])
        if safe:
            safe_ids.add(root_id)

    workset = getattr(renderer, "_psx_native_flow_viewport_workset", None)
    if workset is None:
        workset = GridViewportWorkset()
        renderer._psx_native_flow_viewport_workset = workset
    batch = tuple(grouped)
    skipped = workset.plan(
        root_ids=group_roots, batch=batch, widgets=widgets,
        viewport_height=float(height), epoch=epoch, backend=backend,
        safe_ids=safe_ids, viewport_top=viewport_top,
    )
    return FlowViewportPlan(workset, group_roots, batch, widgets,
                            float(height), epoch, backend, skipped,
                            viewport_top, scroll_host)
