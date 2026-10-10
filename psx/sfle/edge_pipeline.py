"""Constrained edge-aware integration of already-resolved CSS Flex item boxes.

Inputs are content-box flex bases and pre-resolved *nonnegative* physical
padding, borders and margins. Auto margins, signed margins, intrinsic/percentage
lengths and automatic minimum-size rules remain explicitly unsupported here.
The flex solver acts on content bases while fixed edges consume line free space.
"""

from __future__ import annotations

from dataclasses import dataclass

from .box_geometry import UsedBoxEdges, used_box_rect
from .flex_math import FlexBasis, _number, resolve_flexible_lengths
from .line_layout import (
    FlexDirection, FlexWrap, ResolvedItem, form_flex_lines, place_resolved_lines,
)
from .model import BoxRect, WritingDirection


@dataclass(frozen=True, slots=True)
class ResolvedEdgeItem:
    node_id: str
    flex: FlexBasis
    cross_content_size: float
    edges: UsedBoxEdges = UsedBoxEdges()
    order: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be a nonempty string.")
        if not isinstance(self.flex, FlexBasis):
            raise TypeError("flex must be an already-resolved FlexBasis.")
        cross = _number(self.cross_content_size, "cross_content_size")
        if cross < 0:
            raise ValueError("cross_content_size cannot be negative.")
        object.__setattr__(self, "cross_content_size", cross)
        if not isinstance(self.edges, UsedBoxEdges):
            raise TypeError("edges must be UsedBoxEdges.")
        if type(self.order) is not int:
            raise TypeError("order must be a signed integer.")
        margin = self.edges.margin
        if any(x < 0 for x in (margin.top, margin.right, margin.bottom, margin.left)):
            raise ValueError("Signed margins require a later CSS-aware sizing implementation.")


@dataclass(frozen=True, slots=True)
class EdgeLayout:
    lines: tuple[tuple[str, ...], ...]
    boxes: tuple[tuple[str, BoxRect], ...]


def compute_edge_layout(
    items: tuple[ResolvedEdgeItem, ...],
    width: float,
    height: float,
    *,
    direction: FlexDirection = FlexDirection.ROW,
    writing: WritingDirection = WritingDirection.LTR,
    wrap: FlexWrap = FlexWrap.NOWRAP,
    main_gap: float = 0.0,
    cross_gap: float = 0.0,
) -> EdgeLayout:
    """Return resolved item box trees in physical top-left coordinates.

    Lines are formed from hypothetical *outer* main sizes. Fixed used edges
    are reserved before flexing content sizes, then the outer rectangles are
    placed. It is not a replacement for CSS cross-axis alignment or sizing.
    """

    if not isinstance(items, tuple) or not all(isinstance(i, ResolvedEdgeItem) for i in items):
        raise TypeError("items must be an immutable tuple of ResolvedEdgeItem.")
    if len({i.node_id for i in items}) != len(items):
        raise ValueError("node IDs must be unique.")
    if not isinstance(direction, FlexDirection) or not isinstance(writing, WritingDirection):
        raise TypeError("direction and writing must be enum values.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    w, h = _number(width, "width"), _number(height, "height")
    mg, cg = _number(main_gap, "main_gap"), _number(cross_gap, "cross_gap")
    if min(w, h, mg, cg) < 0:
        raise ValueError("Container dimensions and gaps must not be negative.")
    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    main_extent = w if horizontal else h

    def main_edges(i: ResolvedEdgeItem) -> float:
        e = i.edges
        return (e.margin.horizontal + e.padding.horizontal + e.border.horizontal
                if horizontal else e.margin.vertical + e.padding.vertical + e.border.vertical)

    def cross_edges(i: ResolvedEdgeItem) -> float:
        e = i.edges
        return (e.margin.vertical + e.padding.vertical + e.border.vertical
                if horizontal else e.margin.horizontal + e.padding.horizontal + e.border.horizontal)

    hypothetical = tuple(
        ResolvedItem(i.node_id, i.flex.hypothetical + main_edges(i),
                     i.cross_content_size + cross_edges(i), i.order)
        for i in items
    )
    lines = form_flex_lines(hypothetical, main_extent, mg, wrap)
    index = {i.node_id: i for i in items}
    sized: list[tuple[ResolvedItem, ...]] = []
    for line in lines:
        fixed = sum(main_edges(index[i.node_id]) for i in line)
        if fixed > main_extent:
            # Overflow is legal CSS behavior: the available *content* main size
            # is zero rather than a negative value. No implicit clipping.
            free_for_content = 0.0
        else:
            free_for_content = main_extent - fixed
        targets = resolve_flexible_lengths(
            tuple(index[i.node_id].flex for i in line), free_for_content, mg
        )
        sized.append(tuple(
            ResolvedItem(i.node_id, content + main_edges(index[i.node_id]),
                         i.cross_size, i.order)
            for i, content in zip(line, targets)
        ))
    placed = place_resolved_lines(
        tuple(sized), w, h, direction=direction, writing=writing,
        wrap=wrap, main_gap=mg, cross_gap=cg,
    )
    return EdgeLayout(
        placed.lines,
        tuple(
            (p.node_id, used_box_rect(p.rect, index[p.node_id].edges))
            for p in placed.items
        ),
    )
