"""Integrated resolved Flex line breaking, sizing and signed/auto main margins.

The output intentionally contains border/padding/content rectangles, not a
fabricated margin Rect: CSS negative margins can yield negative outer sizes.
Cross-axis auto margins override resolved non-stretch item alignment.
"""

from __future__ import annotations

from dataclasses import dataclass

from .box_geometry import UsedBoxEdges, UsedEdges
from .cross_margins import position_cross_margins
from .cross_alignment import CrossAlign, resolve_cross_alignment
from .cross_stretch import resolve_cross_stretch
from .baseline import BaselineItem, measure_baseline_group, position_baseline_item
from .errors import DiagnosticCode, SFLECapabilityError
from .align_content import AlignContent, distribute_cross_lines
from .flex_math import FlexBasis, _number, resolve_flexible_lengths
from .line_layout import FlexDirection, FlexWrap
from .main_margins import MarginItem, UsedMargin, position_main_margins
from .main_alignment import JustifyContent
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
    cross_start: UsedMargin = UsedMargin()
    cross_end: UsedMargin = UsedMargin()
    align_self: CrossAlign = CrossAlign.AUTO
    cross_size_auto: bool = False
    min_cross_content_size: float = 0.0
    max_cross_content_size: float | None = None
    baseline_from_cross_start: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be nonempty.")
        if not isinstance(self.flex, FlexBasis) or not isinstance(self.edges, UsedBoxEdges):
            raise TypeError("flex and edges must be normalized.")
        if any(not isinstance(margin, UsedMargin) for margin in (
            self.main_start, self.main_end, self.cross_start, self.cross_end
        )):
            raise TypeError("margins must be UsedMargin.")
        if not isinstance(self.align_self, CrossAlign):
            raise TypeError("align_self must be CrossAlign.")
        if type(self.cross_size_auto) is not bool:
            raise TypeError("cross_size_auto must be bool.")
        minimum = _number(self.min_cross_content_size, "min_cross_content_size")
        maximum = (None if self.max_cross_content_size is None else
                   _number(self.max_cross_content_size, "max_cross_content_size"))
        if minimum < 0 or (maximum is not None and maximum < 0):
            raise ValueError("Cross size constraints must be nonnegative.")
        if self.baseline_from_cross_start is not None:
            baseline = _number(self.baseline_from_cross_start, "baseline_from_cross_start")
            if not 0 <= baseline <= _number(self.cross_content_size, 'cross_content_size'):
                raise ValueError("Measured baseline must lie within cross content size.")
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
    used_cross_start_margin: float = 0.0
    used_cross_end_margin: float = 0.0


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
    justify: JustifyContent = JustifyContent.FLEX_START,
    align_items: CrossAlign = CrossAlign.FLEX_START,
    align_content: AlignContent = AlignContent.FLEX_START,
) -> MarginFlexLayout:
    """Form lines with signed outer hypothetical sizes, flex each, place borders.

    CSS §9.3 counts AUTO margins as zero for line fitting. CSS §9.7 reserves
    signed fixed outer contributions, then CSS §8.1 shares positive remaining
    free space across auto margins. Cross auto margins use resolved line sizes;
    alignment/stretch and baseline are not handled.
    """
    if not isinstance(items, tuple) or any(not isinstance(i, MarginFlexItem) for i in items):
        raise TypeError("items must be tuple[MarginFlexItem, ...].")
    if len({i.node_id for i in items}) != len(items):
        raise ValueError("duplicate node IDs.")
    if not isinstance(direction, FlexDirection) or not isinstance(writing, WritingDirection):
        raise TypeError("direction/writing must be enums.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    if not isinstance(justify, JustifyContent):
        raise TypeError("justify must be JustifyContent.")
    if not isinstance(align_items, CrossAlign) or align_items == CrossAlign.AUTO:
        raise TypeError("align_items must be a non-auto CrossAlign.")
    if not isinstance(align_content, AlignContent):
        raise TypeError("align_content must be AlignContent.")
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

    # Baseline metrics are supplied by a measurement port, never fabricated.
    # This restricted slice only supports the horizontal first-baseline group.
    baseline_groups = []
    for line in lines:
        selected = [item for item in line
                    if (align_items if item.align_self == CrossAlign.AUTO
                        else item.align_self) == CrossAlign.BASELINE
                    and item.cross_start.value is not None
                    and item.cross_end.value is not None]
        if selected and not horizontal:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Column baseline needs orthogonal baseline measurement.",
            )
        metrics = []
        for item in selected:
            if item.baseline_from_cross_start is None:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Baseline requires a measured cross-content baseline offset.",
                )
            edges = item.edges
            offset = (edges.border.top + edges.padding.top +
                      item.baseline_from_cross_start)
            metrics.append(BaselineItem(
                cross_border(item),
                item.cross_start.value, item.cross_end.value, offset,
            ))
        baseline_groups.append(measure_baseline_group(tuple(metrics)) if metrics else None)

    # CSS nowrap has the container's inner cross size as its line size.
    # Wrapped lines use the largest hypothetical outer cross size of their
    # members. AUTO margins count as zero when establishing line size.
    cross_extent = h if horizontal else w
    line_cross_sizes = tuple(
        cross_extent if wrap == FlexWrap.NOWRAP else max(
            0.0,
            *(cross_border(item) + (item.cross_start.value or 0.0)
              + (item.cross_end.value or 0.0) for item in line),
            *( (baseline_groups[index].extent,)
               if baseline_groups[index] is not None else () ),
        )
        for index, line in enumerate(lines)
    )
    cross_forward = (True if horizontal else writing == WritingDirection.LTR)
    if wrap == FlexWrap.WRAP_REVERSE:
        cross_forward = not cross_forward
    distribution = distribute_cross_lines(
        align_content, cross_extent, line_cross_sizes, gap=cg,
        forward=cross_forward, nowrap=wrap == FlexWrap.NOWRAP,
    )
    line_cross_sizes = distribution.sizes
    line_starts = distribution.starts

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
            borders, main_extent, main_gap=mg, direction=direction, writing=writing,
            justify=justify,
        )
        for item, pos in zip(line, positioned):
            cross_size = cross_border(item)
            chosen_align = align_items if item.align_self == CrossAlign.AUTO else item.align_self
            if (
                chosen_align == CrossAlign.STRETCH
                and item.cross_size_auto
                and item.cross_start.value is not None
                and item.cross_end.value is not None
            ):
                edges = item.edges
                pb_cross = (edges.border.vertical + edges.padding.vertical if horizontal
                            else edges.border.horizontal + edges.padding.horizontal)
                stretched = resolve_cross_stretch(
                    line_cross_sizes[line_index], pb_cross,
                    item.cross_start.value, item.cross_end.value,
                    min_content_size=item.min_cross_content_size,
                    max_content_size=item.max_cross_content_size,
                )
                cross_size = stretched.border_size
            cross_pos = position_cross_margins(
                cross_size, line_cross_sizes[line_index],
                start=item.cross_start, end=item.cross_end,
                cross_forward=cross_forward,
            )
            cross_origin = line_starts[line_index]
            # Auto cross margins have precedence over align-items/align-self.
            if item.cross_start.value is None or item.cross_end.value is None:
                cross_offset = cross_pos.border_start
            elif chosen_align == CrossAlign.BASELINE:
                group = baseline_groups[line_index]
                if group is None:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE, "Missing baseline group.",
                    )
                edges = item.edges
                metric = BaselineItem(
                    cross_size, item.cross_start.value, item.cross_end.value,
                    edges.border.top + edges.padding.top + item.baseline_from_cross_start,
                )
                cross_offset = position_baseline_item(
                    metric, group, line_cross_sizes[line_index],
                    cross_forward=cross_forward,
                )
            elif chosen_align == CrossAlign.STRETCH:
                # A definite cross size, or an auto size just stretched above,
                # takes the cross-start position (not a second sizing pass).
                cross_offset = (item.cross_start.value if cross_forward else
                                line_cross_sizes[line_index] - item.cross_start.value - cross_size)
            else:
                cross_offset = resolve_cross_alignment(
                    align_items, item.align_self, cross_size,
                    line_cross_sizes[line_index],
                    item.cross_start.value, item.cross_end.value,
                    cross_forward=cross_forward,
                )
            border_cross_start = cross_origin + cross_offset
            border = (
                Rect(pos.border_start, border_cross_start, pos.border_main_size, cross_size)
                if horizontal else
                Rect(border_cross_start, pos.border_start, cross_size, pos.border_main_size)
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
                cross_pos.used_start_margin, cross_pos.used_end_margin,
            ))
    return MarginFlexLayout(tuple(tuple(item.node_id for item in line) for line in lines),
                            tuple(output))
