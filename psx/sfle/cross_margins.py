"""Resolved CSS Flexbox cross-axis margin positioning for an existing flex line.

Consumes known flex-line cross size and border-box cross size. In this
restricted kernel, the line's cross size must already be established by the
caller; no align-content, stretch or baseline sizing happens here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flex_math import _number
from .main_margins import UsedMargin
from .fixed_point import LayoutUnit


def _unit(value: float) -> float:
    return LayoutUnit.from_nearest(value).to_px()


def _sub(value: float, *deductions: float) -> float:
    total = LayoutUnit.from_nearest(value)
    for deduction in deductions:
        total = total - LayoutUnit.from_nearest(deduction)
    return total.to_px()


@dataclass(frozen=True, slots=True)
class CrossMarginPosition:
    border_start: float
    used_start_margin: float
    used_end_margin: float


def position_cross_margins(
    border_cross_size: float,
    line_cross_size: float,
    *,
    start: UsedMargin = UsedMargin(),
    end: UsedMargin = UsedMargin(),
    cross_forward: bool = True,
) -> CrossMarginPosition:
    """Return physical cross-axis border start relative to the flex line.

    For positive space auto cross margins share it equally. For overflow,
    the cross-start auto margin resolves to zero and the opposite auto
    margin receives the negative remainder (where applicable). Fixed signed
    margins are never silently rewritten.

    The caller maps cross-start to top/left or bottom/right based on
    horizontal writing direction and wrap-reverse.
    """
    border = _unit(_number(border_cross_size, "border_cross_size"))
    line = _unit(_number(line_cross_size, "line_cross_size"))
    if min(border, line) < 0:
        raise ValueError("Cross sizes cannot be negative.")
    if not isinstance(start, UsedMargin) or not isinstance(end, UsedMargin):
        raise TypeError("Cross margins must be UsedMargin.")
    if type(cross_forward) is not bool:
        raise TypeError("cross_forward must be bool.")

    start_fixed = 0.0 if start.value is None else _unit(start.value)
    end_fixed = 0.0 if end.value is None else _unit(end.value)
    free = _sub(line, border, start_fixed, end_fixed)
    auto_count = int(start.value is None) + int(end.value is None)
    if auto_count and free > 0:
        share = _unit(free / auto_count)
        used_start = share if start.value is None else start_fixed
        used_end = share if end.value is None else end_fixed
    elif auto_count and free <= 0:
        used_start = 0.0 if start.value is None else start_fixed
        used_end = (
            _sub(line, border, used_start) if end.value is None
            else end_fixed
        )
    else:
        used_start, used_end = start_fixed, end_fixed

    position = _unit(used_start if cross_forward else _sub(line, used_start, border))
    return CrossMarginPosition(position, used_start, used_end)
