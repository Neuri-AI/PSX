"""Historical Flex-basis normalization with shared CSS size reference types."""
from __future__ import annotations

from psx.layout.projection.box_sizing import (
    BoxSizing, GapPhase, UsedBoxSize, resolve_percentage_gap,
    normalize_box_size,
)
from psx.layout.fallback.flex_math import _number
def normalize_flex_box_basis(
    basis: float,
    padding_border: float,
    sizing: BoxSizing,
    *,
    min_size: float = 0.0,
    max_size: float | None = None,
    grow: float = 0.0,
    shrink: float = 1.0,
) -> "FlexBasis":
    """Normalize definite CSS flex-basis and min/max to content-box units.

    CSS box-sizing determines which box a definite flex basis and definite
    min/max main-size constraints describe. The padding/border floor is
    subtracted from border-box constraints; if max < min, min wins per CSS.
    No percentages, auto minima or intrinsically determined bounds are
    implicitly resolved by this helper.
    """

    from psx.layout.fallback.flex_math import FlexBasis

    used_basis = normalize_box_size(basis, padding_border, sizing).content
    used_minimum = normalize_box_size(min_size, padding_border, sizing).content
    used_maximum = (
        normalize_box_size(max_size, padding_border, sizing).content
        if max_size is not None else None
    )
    if used_maximum is not None and used_maximum < used_minimum:
        used_maximum = used_minimum
    hypothetical = max(used_basis, used_minimum)
    if used_maximum is not None:
        hypothetical = min(hypothetical, used_maximum)
    return FlexBasis(
        basis=used_basis, hypothetical=hypothetical, min_size=used_minimum,
        max_size=used_maximum, grow=grow, shrink=shrink,
    )
