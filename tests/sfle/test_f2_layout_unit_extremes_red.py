"""RED D-F1.13: exact raw-signed LayoutUnit conversions and saturation.

Based on Chromium 153.0.8010.12 FixedPoint<6,int32_t>. These are mandatory
stage-level tests; a passing DOM snapshot alone misses overflow and tie bugs.
"""
import math
import pytest

from psx.sfle.fixed_point import LayoutUnit, I32_MIN, I32_MAX


@pytest.mark.parametrize(("value", "trunc", "floor", "ceil", "nearest"), [
    (0.0, 0, 0, 0, 0),
    (1 / 128, 0, 0, 1, 1),
    (-1 / 128, 0, -1, 0, -1),
    (3 / 128, 1, 1, 2, 2),
    (-3 / 128, -1, -2, -1, -2),
    (13 / 64, 13, 13, 13, 13),
    (-13 / 64, -13, -13, -13, -13),
])
def test_chromium_153_distinct_conversions(value, trunc, floor, ceil, nearest):
    assert LayoutUnit.from_trunc(value).raw == trunc
    assert LayoutUnit.from_floor(value).raw == floor
    assert LayoutUnit.from_ceil(value).raw == ceil
    assert LayoutUnit.from_nearest(value).raw == nearest
    assert LayoutUnit.from_nearest(value).to_px() == nearest / 64


@pytest.mark.parametrize(("a", "b", "sum_raw"), [
    (I32_MAX, 1, I32_MAX),
    (I32_MIN, -1, I32_MIN),
    (I32_MAX, I32_MAX, I32_MAX),
    (I32_MIN, I32_MIN, I32_MIN),
    (-100, 75, -25),
])
def test_saturating_add_raw_integer_overflow(a, b, sum_raw):
    assert (LayoutUnit.from_raw(a) + LayoutUnit.from_raw(b)).raw == sum_raw


def test_saturation_of_conversions_and_64_bit_intermediates():
    assert LayoutUnit.from_trunc(1e20).raw == I32_MAX
    assert LayoutUnit.from_trunc(-1e20).raw == I32_MIN
    assert LayoutUnit.from_floor(1e20).raw == I32_MAX
    assert LayoutUnit.from_ceil(-1e20).raw == I32_MIN
    assert LayoutUnit.from_raw(I32_MAX + 100).raw == I32_MAX
    assert LayoutUnit.from_raw(I32_MIN - 100).raw == I32_MIN
    assert LayoutUnit.from_raw(80).mul_div(LayoutUnit.from_raw(I32_MAX),
                                           LayoutUnit.from_raw(160)).raw == 1073741823


def test_invalid_nonfinite_input_must_not_be_coerced_to_zero():
    for number in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            LayoutUnit.from_nearest(number)


@pytest.mark.parametrize("fraction,reference,expected", (
    (1e200, 1e200, I32_MAX / 64),
    (-1e200, 1e200, I32_MIN / 64),
))
def test_finite_percent_operands_overflow_to_saturated_layout_units(
    fraction, reference, expected,
):
    # Finite CSS tokens can overflow f64 in percent * containing-block
    # reference. Both engines must saturate the signed i32 raw result,
    # never throw ValueError, yield infinity or panic.
    from psx.sfle.compute_alpha import (
        _percent_used_dimension, _percent_flex_basis_used, _used_gap,
    )
    from psx.sfle.lengths import Length
    assert _percent_used_dimension(fraction, reference) == expected
    assert _percent_flex_basis_used(fraction, reference) == expected
    if fraction > 0:
        assert _used_gap(Length.percent(fraction), reference, "child") == expected
