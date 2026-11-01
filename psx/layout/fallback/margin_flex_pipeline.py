"""Integrated resolved Flex line breaking, sizing and signed/auto main margins.

The output intentionally contains border/padding/content rectangles, not a
fabricated margin Rect: CSS negative margins can yield negative outer sizes.
Cross-axis auto margins override resolved non-stretch item alignment.
"""

from __future__ import annotations

from psx.layout.contracts.recursive_tree import MarginFlexItem, MarginFlexBox, MarginFlexLayout

from dataclasses import dataclass

from psx.layout.fallback.box_geometry import UsedBoxEdges, UsedEdges
from psx.layout.fallback.cross_margins import position_cross_margins
from psx.layout.fallback.cross_alignment import CrossAlign, resolve_cross_alignment
from psx.layout.fallback.cross_stretch import resolve_cross_stretch
from psx.layout.fallback.baseline import BaselineItem, measure_baseline_group, position_baseline_item
from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError
from psx.layout.fallback.align_content import AlignContent, distribute_cross_lines
from psx.layout.fallback.flex_math import FlexBasis, _number, resolve_flexible_lengths
from psx.layout.fallback.line_layout import FlexDirection, FlexWrap
from psx.layout.fallback.main_margins import MarginItem, UsedMargin, position_main_margins
from psx.layout.fallback.main_alignment import JustifyContent
from psx.layout.contracts.model import Rect, WritingDirection
from psx.layout.contracts.fixed_point import LayoutUnit


def _layout_unit(value: float) -> float:
    return LayoutUnit.from_nearest(value).to_px()


def _sum_units(*values: float) -> float:
    """Accumulate geometry as saturating LayoutUnits at every edge."""
    total = LayoutUnit.from_raw(0)
    for value in values:
        total = total + LayoutUnit.from_nearest(value)
    return total.to_px()


def _subtract_units(value: float, *deductions: float) -> float:
    total = LayoutUnit.from_nearest(value)
    for deduction in deductions:
        total = total - LayoutUnit.from_nearest(deduction)
    return total.to_px()


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
    w, h, mg, cg = (_layout_unit(_number(v, k)) for v, k in (
        (width, "width"), (height, "height"), (main_gap, "main_gap"), (cross_gap, "cross_gap")
    ))
    if min(w, h, mg, cg) < 0:
        raise ValueError("container dimensions and gaps must be nonnegative.")
    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    main_extent = w if horizontal else h

    def main_fixed(item: MarginFlexItem) -> float:
        edges = item.edges
        pb = _sum_units(edges.border.horizontal, edges.padding.horizontal) if horizontal else (
            _sum_units(edges.border.vertical, edges.padding.vertical)
        )
        return _sum_units(pb, item.main_start.value or 0.0, item.main_end.value or 0.0)

    def cross_border(item: MarginFlexItem) -> float:
        edges = item.edges
        return _sum_units(item.cross_content_size, (
            _sum_units(edges.border.vertical, edges.padding.vertical) if horizontal else
            _sum_units(edges.border.horizontal, edges.padding.horizontal)
        )
        )

    ordered = sorted(enumerate(items), key=lambda pair: (pair[1].order, pair[0]))
    lines: list[list[MarginFlexItem]] = []
    current: list[MarginFlexItem] = []
    occupied = 0.0
    for _, item in ordered:
        hypothetical_outer = _sum_units(item.flex.hypothetical, main_fixed(item))
        candidate = _sum_units(occupied, mg if current else 0.0, hypothetical_outer)
        if wrap != FlexWrap.NOWRAP and current and candidate > main_extent:
            lines.append(current)
            current, occupied = [item], hypothetical_outer
        else:
            current.append(item)
            occupied = candidate
    if current:
        lines.append(current)

    # Baseline metrics are supplied by a measurement port, never fabricated.
    # The adapter supplies the baseline on the active cross axis for both
    # row and column contexts; geometry does not infer one from box bounds.
    baseline_groups = []
    for line in lines:
        selected = [item for item in line
                    if (align_items if item.align_self == CrossAlign.AUTO
                        else item.align_self) == CrossAlign.BASELINE
                    and item.cross_start.value is not None
                    and item.cross_end.value is not None]
        metrics = []
        for item in selected:
            if item.baseline_from_cross_start is None:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Baseline requires a measured cross-content baseline offset.",
                )
            edges = item.edges
            offset = _sum_units(
                edges.border.top if horizontal else edges.border.left,
                edges.padding.top if horizontal else edges.padding.left,
                item.baseline_from_cross_start,
            )
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
            *(_sum_units(cross_border(item), item.cross_start.value or 0.0,
                         item.cross_end.value or 0.0) for item in line),
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
        fixed = _sum_units(*(main_fixed(item) for item in line))
        content_available = max(0.0, _subtract_units(main_extent, fixed))
        targets = resolve_flexible_lengths(
            tuple(item.flex for item in line), content_available, mg
        )
        borders = tuple(
            MarginItem(
                item.node_id,
                _sum_units(content_size, item.edges.border.horizontal,
                           item.edges.padding.horizontal)
                if horizontal else _sum_units(content_size, item.edges.border.vertical,
                                               item.edges.padding.vertical),
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
                pb_cross = (_sum_units(edges.border.vertical, edges.padding.vertical) if horizontal
                            else _sum_units(edges.border.horizontal, edges.padding.horizontal))
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
                    _sum_units(
                        edges.border.top if horizontal else edges.border.left,
                        edges.padding.top if horizontal else edges.padding.left,
                        item.baseline_from_cross_start,
                    ),
                )
                cross_offset = position_baseline_item(
                    metric, group, line_cross_sizes[line_index],
                    cross_forward=cross_forward,
                )
            elif chosen_align == CrossAlign.STRETCH:
                # A definite cross size, or an auto size just stretched above,
                # takes the cross-start position (not a second sizing pass).
                cross_offset = (item.cross_start.value if cross_forward else
                                _subtract_units(line_cross_sizes[line_index],
                                                item.cross_start.value, cross_size))
            else:
                cross_offset = resolve_cross_alignment(
                    align_items, item.align_self, cross_size,
                    line_cross_sizes[line_index],
                    item.cross_start.value, item.cross_end.value,
                    cross_forward=cross_forward,
                )
            border_cross_start = _sum_units(cross_origin, cross_offset)
            border = (
                Rect(pos.border_start, border_cross_start, pos.border_main_size, cross_size)
                if horizontal else
                Rect(border_cross_start, pos.border_start, cross_size, pos.border_main_size)
            )
            e = item.edges
            padding = Rect(
                _sum_units(border.x, e.border.left), _sum_units(border.y, e.border.top),
                _subtract_units(border.width, e.border.horizontal),
                _subtract_units(border.height, e.border.vertical),
            )
            content = Rect(
                _sum_units(padding.x, e.padding.left), _sum_units(padding.y, e.padding.top),
                _subtract_units(padding.width, e.padding.horizontal),
                _subtract_units(padding.height, e.padding.vertical),
            )
            output.append(MarginFlexBox(
                item.node_id, content, padding, border,
                pos.used_start_margin, pos.used_end_margin, line_index,
                cross_pos.used_start_margin, cross_pos.used_end_margin,
            ))
    return MarginFlexLayout(tuple(tuple(item.node_id for item in line) for line in lines),
                            tuple(output))
