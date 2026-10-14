"""Point 3: resolved f64 pre-quantization must not leak nonfinite geometry.

These low-level CSS Flex math helpers are intentionally floating-point; unlike
LayoutUnit stages they must fail closed when finite input overflows f64.
"""
import pytest
from psx.sfle.flex_math import FlexBasis, resolve_flexible_lengths


@pytest.mark.parametrize("gap", (1e308, 1.7976931348623157e308))
def test_resolved_flex_rejects_finite_gap_times_count_overflow(gap):
    items=tuple(FlexBasis(1,1,grow=0,shrink=1) for _ in range(4))
    with pytest.raises(ValueError,match="overflow|nonfinite"):
        resolve_flexible_lengths(items,100.0,gap)


def test_resolved_flex_rejects_sum_of_finite_hypothetical_bases_overflow():
    items=(FlexBasis(1e308,1e308),FlexBasis(1e308,1e308))
    with pytest.raises(ValueError,match="overflow|nonfinite"):
        resolve_flexible_lengths(items,100.0,0.0)


def test_resolved_flex_rejects_overflowing_weighted_shrink_factor():
    items=(
        FlexBasis(1e308,1e308,shrink=1e308),
        FlexBasis(1,1,shrink=1),
    )
    with pytest.raises(ValueError,match="overflow|nonfinite"):
        resolve_flexible_lengths(items,100.0)


def test_resolved_flex_rejects_overflowing_aggregate_grow_factor():
    items=(
        FlexBasis(1,1,grow=1e308),
        FlexBasis(1,1,grow=1e308),
    )
    with pytest.raises(ValueError,match="overflow|nonfinite"):
        resolve_flexible_lengths(items,100.0)
