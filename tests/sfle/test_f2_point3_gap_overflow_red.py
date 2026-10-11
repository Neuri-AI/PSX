"""F2 point 3: gap multiplication and repeated spacing must saturate per LayoutUnit.

Test the stage directly so browser-sized fixtures cannot hide signed i32
overflow or per-gap fractional rounding errors in many-item alignment.
"""
import pytest

from psx.sfle.fixed_point import I32_MAX, SCALE
from psx.sfle.main_alignment import JustifyContent, resolve_main_alignment
from psx.sfle.align_content import AlignContent, distribute_cross_lines

MAX=I32_MAX/SCALE


@pytest.mark.parametrize("count", (3, 4, 12, 128))
@pytest.mark.parametrize("gap", (MAX, 1e308))
def test_main_alignment_gap_multiplication_saturates(count, gap):
    result=resolve_main_alignment(
        JustifyContent.FLEX_START, 0.0, (0.0,)*count, gap=gap,
    )
    assert result.remaining_free_space == -MAX
    assert result.leading_space == 0.0
    assert 0.0 <= result.between_space <= MAX


@pytest.mark.parametrize("count", (3, 4, 12, 128))
def test_main_alignment_rounds_each_gutter_before_accumulating(count):
    gap=0.008
    result=resolve_main_alignment(
        JustifyContent.FLEX_START, 20.0, (0.0,)*count, gap=gap,
    )
    assert result.remaining_free_space == 20.0 - (count-1)/SCALE


@pytest.mark.parametrize("count", (3, 4, 16, 128))
def test_multiline_cross_gap_uses_signed_saturated_accumulation(count):
    result=distribute_cross_lines(
        AlignContent.FLEX_START, 0.0, (0.0,)*count, gap=1e308,
    )
    assert result.free_space == -MAX
    assert len(result.starts)==count
    assert all(-MAX-1/SCALE <= x <= MAX for x in result.starts)
