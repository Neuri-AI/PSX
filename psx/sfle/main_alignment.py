"""F2.2.3: CSS justify-content distribution after flexible-length resolution.

Pure one-line main-axis alignment. Input border-box sizes and already-used
signed margins are explicit. Automatic margins must have been resolved by the
main-margin stage before calling this function. No browser/native dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .flex_math import _number


class JustifyContent(str, Enum):
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"


@dataclass(frozen=True, slots=True)
class MainAlignment:
    leading_space: float
    between_space: float
    remaining_free_space: float


def resolve_main_alignment(
    justify: JustifyContent,
    available_main: float,
    outer_sizes: tuple[float, ...],
    *,
    gap: float = 0.0,
) -> MainAlignment:
    """Resolve CSS Flexbox §8.2 main distribution for already-sized items.

    On negative free space, space-between behaves as flex-start, and
    space-around/space-evenly behave as safe center (flex-start for overflow).
    center and flex-end remain unsafe and may produce negative leading space.
    Empty lines never require distribution.
    """

    if not isinstance(justify, JustifyContent):
        raise TypeError("justify must be JustifyContent.")
    if not isinstance(outer_sizes, tuple):
        raise TypeError("outer_sizes must be a tuple.")
    extent = _number(available_main, "available_main")
    fixed_gap = _number(gap, "gap")
    sizes = tuple(_number(value, "outer_size") for value in outer_sizes)
    if extent < 0 or fixed_gap < 0:
        raise ValueError("Container and gap must be nonnegative.")
    count = len(sizes)
    free = extent - sum(sizes) - fixed_gap * max(0, count - 1)
    if count == 0:
        return MainAlignment(0.0, fixed_gap, free)

    if justify == JustifyContent.FLEX_START:
        lead, extra = 0.0, 0.0
    elif justify == JustifyContent.FLEX_END:
        lead, extra = free, 0.0
    elif justify == JustifyContent.CENTER:
        lead, extra = free / 2.0, 0.0
    elif justify == JustifyContent.SPACE_BETWEEN:
        lead, extra = 0.0, max(0.0, free) / (count - 1) if count > 1 else 0.0
    elif justify == JustifyContent.SPACE_AROUND:
        if free < 0:
            lead, extra = 0.0, 0.0
        else:
            extra = free / count
            lead = extra / 2.0
    else:
        if free < 0:
            lead, extra = 0.0, 0.0
        else:
            extra = free / (count + 1)
            lead = extra
    return MainAlignment(lead, fixed_gap + extra, free)
