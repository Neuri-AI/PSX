"""Integrated resolved Flex line breaking, sizing and signed/auto main margins.

The output intentionally contains border/padding/content rectangles, not a
fabricated margin Rect: CSS negative margins can yield negative outer sizes.
Only zero cross-axis margins and start-aligned cross sizes are supported.
"""

from __future__ import annotations

from dataclasses import dataclass

from .box_geometry import UsedBoxEdges, UsedEdges
from .flex_math import FlexBasis, _number, resolve_flexible_lengths
from .line_layout import FlexDirection, FlexWrap, ResolvedItem, place_resolved_lines
from .main_margins import MarginItem, UsedMargin, position_main_margins
from .model import Rect, WritingDirection


@dataclass(frozen=True, slots=True)
class MarginFlexItem:
    node_id: str
    flex: FlexBasis
    cross_content_size: float
    edges: UsedBoxEdges = UsedBoxEdges()
    main_start: UsedMargin = UsedMargin()
    main_end: UsedMargin = UsedMargin()
    order: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be nonempty.")
        if not isinstance(self.flex, FlexBasis) or not isinstance(self.edges, UsedBoxEdges):
            raise TypeError("flex and edges must be normalized.")
        if not isinstance(self.main_start, UsedMargin) or not isinstance(self.main_end, UsedMargin):
            raise TypeError("main margins must be UsedMargin.")
        if self.edges.margin != UsedEdges():
            raise ValueError("Set all physical margins to zero; use main_start/main_end.")
        if type(self.order) is not int:
            raise TypeError("order must be a signed integer.")
        size = _number(self.cross_content_size, "cross_content_size")
        if size < 0:
            raise ValueError("cross size cannot be negative.")
        object.__setattr__(self, "cross_content_size", size)


@dataclass(frozen=True, slots=True)
class MarginFlexBox:
    node_id: str
    content: Rect
    padding: Rect
    border: Rect
    used_main_start_margin: float
    used_main_end_margin: float
    line_index: int


@dataclass(frozen=True, slots=True)
class MarginFlexLayout:
    lines: tuple[tuple[str, ...], ...]
    boxes: tuple[MarginFlexBox, ...]


def compute_margin_flex_layout(
    items: tuple[MarginFlexItem, ...], width: float, height: float, *,
    direction: FlexDirection = FlexDirection.ROW,
    writing: WritingDirection = WritingDirection.LTR,
    wrap: FlexWrap = FlexWrap.NOWRAP,
    main_gap: float = 0.0,
    cross_gap: float = 0.0,
) -> MarginFlexLayout:
    """Form lines with signed outer hypothetical sizes, flex each, place borders.

    CSS §9.3 counts AUTO margins as zero for line fitting. CSS §9.7 reserves
    signed fixed outer contributions, then CSS §8.1 shares positive remaining
    free space across auto margins. The cross axis is start-aligned only.
    """
    if not isinstance(items, tuple) or any(not isinstance(i, MarginFlexItem) for i in items):
        raise TypeError("items must be tuple[MarginFlexItem, ...].")
    if len({i.node_id for i in items}) != len(items):
        raise ValueError("duplicate node IDs.")
    if not isinstance(direction, FlexDirection) or not isinstance(writing, WritingDirection):
        raise TypeError("direction/writing must be enums.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    w, h, mg, cg = (_number(v, k) for v, k in (
        (width, "width"), (height, "height"), (main_gap, "main_gap"), (cross_gap, "cross_gap")
    ))
    if min(w, h, mg, cg) < 0:
        raise ValueError("container dimensions and gaps must be nonnegative.")
    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    main_extent = w if horizontal else h

    def main_fixed(item: MarginFlexItem) -> float:
        edges = item.edges
        pb = edges.border.horizontal + edges.padding.horizontal if horizontal else (
            edges.border.vertical + edges.padding.vertical
        )
        return pb + (item.main_start.value or 0.0) + (item.main_end.value or 0.0)

    def cross_border(item: MarginFlexItem) -> float:
        edges = item.edges
        return item.cross_content_size + (
            edges.border.vertical + edges.padding.vertical if horizontal else
            edges.border.horizontal + edges.padding.horizontal
        )

    ordered = sorted(enumerate(items), key=lambda pair: (pair[1].order, pair[0]))
    lines: list[list[MarginFlexItem]] = []
    current: list[MarginFlexItem] = []
    occupied = 0.0
    for _, item in ordered:
        hypothetical_outer = item.flex.hypothetical + main_fixed(item)
        candidate = occupied + (mg if current else 0.0) + hypothetical_outer
        if wrap != FlexWrap.NOWRAP and current and candidate > main_extent:
            lines.append(current)
            current, occupied = [item], hypothetical_outer
        else:
            current.append(item)
            occupied = candidate
    if current:
        lines.append(current)

    # Reuse the resolved geometry's cross-line placement. Its synthetic
    # zero-width items do not drive main placement: margins do that explicitly.
    cross_lines = tuple(tuple(
        ResolvedItem(item.node_id, 0.0, cross_border(item), item.order)
        for item in line
    ) for line in lines)
    cross_placement = place_resolved_lines(
        cross_lines, w, h, direction=direction, writing=writing, wrap=wrap,
        main_gap=0.0, cross_gap=cg,
    )
    cross_by_id = {p.node_id: p for p in cross_placement.items}

    output: list[MarginFlexBox] = []
    for line_index, line in enumerate(lines):
        fixed = sum(main_fixed(item) for item in line)
        content_available = max(0.0, main_extent - fixed)
        targets = resolve_flexible_lengths(
            tuple(item.flex for item in line), content_available, mg
        )
        borders = tuple(
            MarginItem(
                item.node_id,
                content_size + (item.edges.border.horizontal + item.edges.padding.horizontal
                                if horizontal else item.edges.border.vertical + item.edges.padding.vertical),
                item.main_start,
                item.main_end,
            )
            for item, content_size in zip(line, targets)
        )
        positioned = position_main_margins(
            borders, main_extent, main_gap=mg, direction=direction, writing=writing
        )
        for item, pos in zip(line, positioned):
            cross = cross_by_id[item.node_id].rect
            border = (
                Rect(pos.border_start, cross.y, pos.border_main_size, cross.height)
                if horizontal else
                Rect(cross.x, pos.border_start, cross.width, pos.border_main_size)
            )
            e = item.edges
            padding = Rect(
                border.x + e.border.left, border.y + e.border.top,
                border.width - e.border.horizontal, border.height - e.border.vertical,
            )
            content = Rect(
                padding.x + e.padding.left, padding.y + e.padding.top,
                padding.width - e.padding.horizontal, padding.height - e.padding.vertical,
            )
            output.append(MarginFlexBox(
                item.node_id, content, padding, border,
                pos.used_start_margin, pos.used_end_margin, line_index,
            ))
    return MarginFlexLayout(tuple(tuple(item.node_id for item in line) for line in lines),
                            tuple(output))
