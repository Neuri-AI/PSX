"""F2.2.3 pure align-content line distribution after flex line formation.

The caller supplies resolved outer cross-size per line and an explicit
container cross size. No implicit measurement, wrapping or baseline logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .flex_math import _number


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
    extent = _number(container_cross_size, "container_cross_size")
    fixed_gap = _number(gap, "gap")
    sizes = tuple(_number(n, "line_cross_size") for n in line_sizes)
    if extent < 0 or fixed_gap < 0 or any(n < 0 for n in sizes):
        raise ValueError("Cross dimensions and gaps must be nonnegative.")
    count = len(sizes)
    if nowrap and count > 1:
        raise ValueError("nowrap cannot have more than one line.")
    if count == 0:
        return CrossLineDistribution((), (), extent)
    if nowrap:
        sizes = (extent,)
    free = extent - sum(sizes) - fixed_gap * (count - 1)
    lead = 0.0
    between = fixed_gap
    if not nowrap:
        if mode == AlignContent.FLEX_END:
            lead = free
        elif mode == AlignContent.CENTER:
            lead = free / 2
        elif mode == AlignContent.SPACE_BETWEEN and count > 1:
            between += max(0.0, free) / (count - 1)
        elif mode == AlignContent.SPACE_AROUND and free > 0:
            between += free / count
            lead = free / (2 * count)
        elif mode == AlignContent.SPACE_EVENLY and free > 0:
            between += free / (count + 1)
            lead = free / (count + 1)
        elif mode == AlignContent.STRETCH and free > 0:
            sizes = tuple(size + free / count for size in sizes)
    cursor = lead if forward else extent - lead
    positions: list[float] = []
    for size in sizes:
        if forward:
            positions.append(cursor)
            cursor += size + between
        else:
            cursor -= size
            positions.append(cursor)
            cursor -= between
    return CrossLineDistribution(tuple(positions), sizes, free)
