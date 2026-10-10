"""F2.2.2: resolved Flexbox main-axis margin distribution.

A separate pure kernel that positions BORDER boxes directly rather than
representing signed margin boxes as nonnegative rectangles. Content/main sizes
and border-box sizes have already been resolved (including min/max). Auto
margins count as zero for line formation/flexing, then absorb positive free
space equally. With negative remaining space, they resolve to zero.

This does not compute cross-axis margins, justify-content, intrinsic sizes,
wrapping, or CSS line breaking. It is deliberately not a complete layout.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flex_math import _number
from .main_alignment import JustifyContent, resolve_main_alignment
from .line_layout import FlexDirection
from .model import WritingDirection


@dataclass(frozen=True, slots=True)
class UsedMargin:
    """A signed fixed CSS margin, or None for an auto margin."""

    value: float | None = 0.0

    def __post_init__(self) -> None:
        if self.value is not None:
            object.__setattr__(self, "value", _number(self.value, "margin"))


@dataclass(frozen=True, slots=True)
class MarginItem:
    node_id: str
    border_main_size: float
    start: UsedMargin = UsedMargin()
    end: UsedMargin = UsedMargin()

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be nonempty.")
        size = _number(self.border_main_size, "border_main_size")
        if size < 0:
            raise ValueError("border_main_size cannot be negative.")
        object.__setattr__(self, "border_main_size", size)
        if not isinstance(self.start, UsedMargin) or not isinstance(self.end, UsedMargin):
            raise TypeError("Margins must be UsedMargin.")


@dataclass(frozen=True, slots=True)
class MarginPosition:
    node_id: str
    border_start: float
    border_main_size: float
    used_start_margin: float
    used_end_margin: float


def position_main_margins(
    items: tuple[MarginItem, ...],
    container_main_size: float,
    *,
    main_gap: float = 0.0,
    direction: FlexDirection = FlexDirection.ROW,
    writing: WritingDirection = WritingDirection.LTR,
    justify: JustifyContent = JustifyContent.FLEX_START,
) -> tuple[MarginPosition, ...]:
    """Apply §8.1 auto margin distribution after main flex-size resolution.

    Output border_start is a physical x or y axis coordinate relative to the
    content-box origin. Logical start/end are mapped into physical positions
    for row/row-reverse/column/column-reverse with LTR/RTL.
    """

    if not isinstance(items, tuple) or not all(isinstance(i, MarginItem) for i in items):
        raise TypeError("items must be a tuple of MarginItem.")
    if not isinstance(direction, FlexDirection) or not isinstance(writing, WritingDirection):
        raise TypeError("Invalid direction or writing enum.")
    if not isinstance(justify, JustifyContent):
        raise TypeError("justify must be JustifyContent.")
    if len({i.node_id for i in items}) != len(items):
        raise ValueError("Item IDs must be unique.")
    extent = _number(container_main_size, "container_main_size")
    gap = _number(main_gap, "main_gap")
    if extent < 0 or gap < 0:
        raise ValueError("Container and gap must be nonnegative.")

    fixed = sum(
        item.border_main_size + (item.start.value or 0.0) + (item.end.value or 0.0)
        for item in items
    ) + gap * max(0, len(items) - 1)
    auto_count = sum(
        int(item.start.value is None) + int(item.end.value is None)
        for item in items
    )
    share = max(0.0, extent - fixed) / auto_count if auto_count else 0.0
    used_outers = tuple(
        item.border_main_size
        + (share if item.start.value is None else item.start.value)
        + (share if item.end.value is None else item.end.value)
        for item in items
    )
    # Auto margins consume positive free space before justify-content.
    effective_justify = (
        JustifyContent.FLEX_START if auto_count and extent > fixed else justify
    )
    alignment = resolve_main_alignment(
        effective_justify, extent, used_outers, gap=gap
    )
    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    reversed_axis = direction in (FlexDirection.ROW_REVERSE, FlexDirection.COLUMN_REVERSE)
    forward = ((writing == WritingDirection.LTR) != reversed_axis) if horizontal else not reversed_axis
    cursor = alignment.leading_space if forward else extent - alignment.leading_space
    out: list[MarginPosition] = []
    for item in items:
        start_margin = share if item.start.value is None else item.start.value
        end_margin = share if item.end.value is None else item.end.value
        if forward:
            border_start = cursor + start_margin
            cursor += start_margin + item.border_main_size + end_margin + alignment.between_space
        else:
            border_start = cursor - start_margin - item.border_main_size
            cursor -= start_margin + item.border_main_size + end_margin + gap
        out.append(MarginPosition(
            item.node_id, border_start, item.border_main_size,
            start_margin, end_margin,
        ))
    return tuple(out)
