"""F2.2.3 pure align-content line distribution after flex line formation.

The caller supplies resolved outer cross-size per line and an explicit
container cross size. No implicit measurement, wrapping or baseline logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .flex_math import _number
from .fixed_point import LayoutUnit


def _unit(value: float) -> float:
    return LayoutUnit.from_nearest(value).to_px()


def _sum(*values: float) -> float:
    total = LayoutUnit.from_raw(0)
    for value in values:
        total = total + LayoutUnit.from_nearest(value)
    return total.to_px()


def _sub(value: float, *deductions: float) -> float:
    total = LayoutUnit.from_nearest(value)
    for deduction in deductions:
        total = total - LayoutUnit.from_nearest(deduction)
    return total.to_px()


class AlignContent(str, Enum):
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"
    STRETCH = "stretch"


@dataclass(frozen=True, slots=True)
class CrossLineDistribution:
    starts: tuple[float, ...]
    sizes: tuple[float, ...]
    free_space: float


def distribute_cross_lines(
    mode: AlignContent,
    container_cross_size: float,
    line_sizes: tuple[float, ...],
    *,
    gap: float = 0.0,
    forward: bool = True,
    nowrap: bool = False,
) -> CrossLineDistribution:
    """Calculate physical line starts in source order.

    In the restricted resolved-input path, nowrap's only line occupies the
    container cross size. For wrapped lines, stretch increases *line* cross
    sizes, not the items themselves; item stretch is a separate later step.
    Negative free space never leads to a negative distribution gap.
    """
    if not isinstance(mode, AlignContent):
        raise TypeError("mode must be AlignContent.")
    if type(forward) is not bool or type(nowrap) is not bool:
        raise TypeError("forward/nowrap must be bool.")
    if not isinstance(line_sizes, tuple):
        raise TypeError("line_sizes must be a tuple.")
    extent = _unit(_number(container_cross_size, "container_cross_size"))
    fixed_gap = _unit(_number(gap, "gap"))
    sizes = tuple(_unit(_number(n, "line_cross_size")) for n in line_sizes)
    if extent < 0 or fixed_gap < 0 or any(n < 0 for n in sizes):
        raise ValueError("Cross dimensions and gaps must be nonnegative.")
    count = len(sizes)
    if nowrap and count > 1:
        raise ValueError("nowrap cannot have more than one line.")
    if count == 0:
        return CrossLineDistribution((), (), extent)
    if nowrap:
        sizes = (extent,)
    free = _sub(extent, _sum(*sizes, *([fixed_gap] * (count - 1))))
    lead = 0.0
    between = fixed_gap
    if not nowrap:
        if mode == AlignContent.FLEX_END:
            lead = free
        elif mode == AlignContent.CENTER:
            lead = free / 2
        elif mode == AlignContent.SPACE_BETWEEN and count > 1:
            between = _sum(between, max(0.0, free) / (count - 1))
        elif mode == AlignContent.SPACE_AROUND and free > 0:
            between = _sum(between, free / count)
            lead = free / (2 * count)
        elif mode == AlignContent.SPACE_EVENLY and free > 0:
            between = _sum(between, free / (count + 1))
            # Blink floors the first space-evenly offset, independently of
            # its rounded interior gap. Both values stay on the 1/64px grid.
            lead = LayoutUnit.from_floor(free / (count + 1)).to_px()
        elif mode == AlignContent.STRETCH and free > 0:
            sizes = tuple(_sum(size, free / count) for size in sizes)
    cursor = _unit(lead if forward else _sub(extent, lead))
    positions: list[float] = []
    for size in sizes:
        if forward:
            positions.append(cursor)
            cursor = _sum(cursor, size, between)
        else:
            cursor = _sub(cursor, size)
            positions.append(cursor)
            cursor = _sub(cursor, between)
    return CrossLineDistribution(tuple(positions), sizes, free)
