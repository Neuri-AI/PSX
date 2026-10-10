"""Integrated, pure SFLE geometry slice for already resolved, zero-edge boxes.

This is intentionally NOT the full CSS Flexbox engine. All child dimensions,
flex bases and min/max constraints have already been resolved by the caller.
No native measurement, percentages, intrinsic sizing, borders, padding, margins,
auto minimum sizes, alignment or nested flex contexts are computed here.

Pipeline: order-modified line breaks on hypothetical sizes (§9.3), flexible
size resolution per line (§9.7), and logical-axis physical positioning.
Unsupported requirements must be rejected by upstream feature gates.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flex_math import FlexBasis, _number, resolve_flexible_lengths
from .line_layout import (
    FlexDirection,
    FlexWrap,
    ResolvedItem,
    ResolvedLines,
    form_flex_lines,
    place_resolved_lines,
)
from .model import WritingDirection


@dataclass(frozen=True, slots=True)
class ResolvedFlexItem:
    """Measured, CSS-normalized item with zero padding/border/margin."""

    node_id: str
    flex: FlexBasis
    cross_size: float
    order: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("ResolvedFlexItem.node_id must be a nonempty string.")
        if not isinstance(self.flex, FlexBasis):
            raise TypeError("ResolvedFlexItem.flex must be a FlexBasis.")
        cross = _number(self.cross_size, "ResolvedFlexItem.cross_size")
        if cross < 0:
            raise ValueError("ResolvedFlexItem.cross_size cannot be negative.")
        object.__setattr__(self, "cross_size", cross)
        if type(self.order) is not int:
            raise TypeError("ResolvedFlexItem.order must be a signed integer.")


def compute_resolved_flex(
    items: tuple[ResolvedFlexItem, ...],
    width: float,
    height: float,
    *,
    direction: FlexDirection = FlexDirection.ROW,
    writing: WritingDirection = WritingDirection.LTR,
    wrap: FlexWrap = FlexWrap.NOWRAP,
    main_gap: float = 0.0,
    cross_gap: float = 0.0,
) -> ResolvedLines:
    """Compute sizes and used rectangles for the restricted resolved subset.

    Order-modified hypothetical sizes choose line membership, not flexed
    targets. Each formed line separately resolves grow/shrink against its
    definite main axis. Physical positioning preserves line membership and
    uses LTR/RTL and the row/column reverse axis mapping.

    The result is an intermediate placement, not a complete LayoutResult.
    """

    if not isinstance(items, tuple) or not all(
        isinstance(item, ResolvedFlexItem) for item in items
    ):
        raise TypeError("items must be a tuple of ResolvedFlexItem.")
    if len({item.node_id for item in items}) != len(items):
        raise ValueError("ResolvedFlexItem.node_id must be unique.")
    if not isinstance(direction, FlexDirection):
        raise TypeError("direction must be FlexDirection.")
    if not isinstance(writing, WritingDirection):
        raise TypeError("writing must be WritingDirection.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    w, h = _number(width, "width"), _number(height, "height")
    main_gap = _number(main_gap, "main_gap")
    cross_gap = _number(cross_gap, "cross_gap")
    if min(w, h, main_gap, cross_gap) < 0:
        raise ValueError("Container extents and gaps cannot be negative.")

    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    main_extent = w if horizontal else h

    hypothetical = tuple(
        ResolvedItem(item.node_id, item.flex.hypothetical, item.cross_size, item.order)
        for item in items
    )
    lines = form_flex_lines(hypothetical, main_extent, main_gap, wrap)
    by_id = {item.node_id: item for item in items}
    sized_lines: list[tuple[ResolvedItem, ...]] = []

    for line in lines:
        flexes = tuple(by_id[item.node_id].flex for item in line)
        targets = resolve_flexible_lengths(flexes, main_extent, main_gap)
        sized_lines.append(tuple(
            ResolvedItem(item.node_id, target, item.cross_size, item.order)
            for item, target in zip(line, targets)
        ))

    return place_resolved_lines(
        tuple(sized_lines), w, h,
        direction=direction,
        writing=writing,
        wrap=wrap,
        main_gap=main_gap,
        cross_gap=cross_gap,
    )
