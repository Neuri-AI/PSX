"""Pure, resolved-input line formation and physical placement for SFLE.

This isolated F2.2 kernel accepts *used* nonnegative outer sizes, definite
container dimensions and fixed gaps. It does not resolve CSS lengths, perform
cross-size stretching or flex grow/shrink, read native widget metrics, or
construct a LayoutResult. It is safe to test independently of any GUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .flex_math import _number
from .model import Rect, WritingDirection


class FlexDirection(str, Enum):
    ROW = "row"
    ROW_REVERSE = "row-reverse"
    COLUMN = "column"
    COLUMN_REVERSE = "column-reverse"


class FlexWrap(str, Enum):
    NOWRAP = "nowrap"
    WRAP = "wrap"
    WRAP_REVERSE = "wrap-reverse"


@dataclass(frozen=True, slots=True)
class ResolvedItem:
    """Outer used border/margin-box sizes, resolved upstream.

    These dimensions are currently a precondition: placement does not model
    negative margins, box edges, intrinsic sizing or flex auto margins.
    """

    node_id: str
    main_size: float
    cross_size: float
    order: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("Resolved item ID must be a nonempty string.")
        for name in ("main_size", "cross_size"):
            value = _number(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative.")
            object.__setattr__(self, name, value)
        if type(self.order) is not int:
            raise TypeError("Resolved item order must be a signed integer.")


@dataclass(frozen=True, slots=True)
class PositionedItem:
    node_id: str
    rect: Rect
    line_index: int


@dataclass(frozen=True, slots=True)
class ResolvedLines:
    """Line membership and physical used-box placement (origin: top-left)."""

    lines: tuple[tuple[str, ...], ...]
    items: tuple[PositionedItem, ...]


def _axes(direction: FlexDirection, writing: WritingDirection) -> tuple[bool, bool, bool]:
    """Return (main_is_horizontal, main_forward, cross_forward).

    Forward means increasing physical x/y. Cross-axis reversal due to
    wrap-reverse is handled separately.
    """

    horizontal = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    reverse = direction in (FlexDirection.ROW_REVERSE, FlexDirection.COLUMN_REVERSE)
    main_forward = (writing == WritingDirection.LTR) != reverse if horizontal else not reverse
    cross_forward = True if horizontal else writing == WritingDirection.LTR
    return horizontal, main_forward, cross_forward


def form_flex_lines(
    items: tuple[ResolvedItem, ...],
    available_main: float,
    main_gap: float = 0.0,
    wrap: FlexWrap = FlexWrap.NOWRAP,
) -> tuple[tuple[ResolvedItem, ...], ...]:
    """Greedy CSS §9.3 line formation with *already resolved* outer sizes.

    A hypothetical item exceeding the available main size still forms its
    own line. This function never shrinks items before deciding line breaks.
    """

    if not isinstance(items, tuple) or not all(isinstance(v, ResolvedItem) for v in items):
        raise TypeError("items must be an immutable tuple of ResolvedItem.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    available = _number(available_main, "available_main")
    gap = _number(main_gap, "main_gap")
    if available < 0 or gap < 0:
        raise ValueError("Available main size and gap must be nonnegative.")
    if not items:
        return ()
    if len({item.node_id for item in items}) != len(items):
        raise ValueError("Resolved item IDs must be unique.")
    ordered = tuple(item for _, item in sorted(
        enumerate(items), key=lambda entry: (entry[1].order, entry[0])
    ))
    if wrap == FlexWrap.NOWRAP:
        return (ordered,)
    lines: list[tuple[ResolvedItem, ...]] = []
    current: list[ResolvedItem] = []
    used = 0.0
    for item in ordered:
        candidate = used + (gap if current else 0.0) + item.main_size
        if current and candidate > available:
            lines.append(tuple(current))
            current = [item]
            used = item.main_size
        else:
            current.append(item)
            used = candidate
    if current:
        lines.append(tuple(current))
    return tuple(lines)


def place_resolved_lines(
    lines: tuple[tuple[ResolvedItem, ...], ...],
    width: float,
    height: float,
    *,
    direction: FlexDirection = FlexDirection.ROW,
    writing: WritingDirection = WritingDirection.LTR,
    wrap: FlexWrap = FlexWrap.NOWRAP,
    main_gap: float = 0.0,
    cross_gap: float = 0.0,
) -> ResolvedLines:
    """Place resolved outer boxes at start/start in logical Flexbox axes.

    The current feature-gated slice uses line cross size = max(item cross
    size). It does **not** implement CSS align-items/align-content/stretch,
    auto margins, baseline, or multi-line flex sizing. Cross overflow remains
    observable in coordinates and never causes implicit clipping.
    """

    if not isinstance(direction, FlexDirection) or not isinstance(writing, WritingDirection):
        raise TypeError("direction/writing must be declared enum members.")
    if not isinstance(wrap, FlexWrap):
        raise TypeError("wrap must be FlexWrap.")
    if not isinstance(lines, tuple) or any(not isinstance(line, tuple) for line in lines):
        raise TypeError("lines must be an immutable tuple of line tuples.")
    w, h = _number(width, "width"), _number(height, "height")
    mg, cg = _number(main_gap, "main_gap"), _number(cross_gap, "cross_gap")
    if min(w, h, mg, cg) < 0:
        raise ValueError("Dimensions and gaps must be nonnegative.")
    flat = [item for line in lines for item in line]
    if any(not isinstance(item, ResolvedItem) for item in flat):
        raise TypeError("Every line item must be ResolvedItem.")
    if len({item.node_id for item in flat}) != len(flat):
        raise ValueError("Resolved item IDs must be unique across lines.")
    if wrap == FlexWrap.NOWRAP and len(lines) > 1:
        raise ValueError("nowrap cannot contain multiple lines.")

    horizontal, main_forward, cross_forward = _axes(direction, writing)
    if wrap == FlexWrap.WRAP_REVERSE:
        cross_forward = not cross_forward
    main_extent = w if horizontal else h
    cross_extent = h if horizontal else w
    cross_cursor = 0.0 if cross_forward else cross_extent
    output: list[PositionedItem] = []
    memberships: list[tuple[str, ...]] = []

    for line_idx, line in enumerate(lines):
        line_cross = max((item.cross_size for item in line), default=0.0)
        if not cross_forward:
            cross_cursor -= line_cross
        cursor = 0.0 if main_forward else main_extent
        line_members: list[str] = []
        for item in line:
            if not main_forward:
                cursor -= item.main_size
            if horizontal:
                rect = Rect(cursor, cross_cursor, item.main_size, item.cross_size)
            else:
                rect = Rect(cross_cursor, cursor, item.cross_size, item.main_size)
            output.append(PositionedItem(item.node_id, rect, line_idx))
            line_members.append(item.node_id)
            cursor += (item.main_size if main_forward else 0.0)
            cursor += mg if main_forward else -mg
        memberships.append(tuple(line_members))
        if cross_forward:
            cross_cursor += line_cross
            if line_idx < len(lines) - 1:
                cross_cursor += cg
        elif line_idx < len(lines) - 1:
            cross_cursor -= cg

    return ResolvedLines(tuple(memberships), tuple(output))
