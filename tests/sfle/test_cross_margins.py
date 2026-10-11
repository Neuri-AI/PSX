"""F2.2.2 resolved cross-axis automatic and signed Flexbox margin tests."""

from __future__ import annotations

import pytest

from psx.sfle.cross_margins import position_cross_margins
from psx.sfle.main_margins import UsedMargin


def test_two_auto_cross_margins_center_with_positive_space():
    result = position_cross_margins(
        20, 100, start=UsedMargin(None), end=UsedMargin(None)
    )
    assert (result.border_start, result.used_start_margin, result.used_end_margin) == (
        40, 40, 40
    )


def test_one_auto_margin_receives_remaining_cross_space():
    result = position_cross_margins(
        20, 100, start=UsedMargin(10), end=UsedMargin(None)
    )
    assert result.border_start == 10
    assert result.used_end_margin == 70


def test_overflow_with_two_auto_margins_keeps_cross_start_zero():
    result = position_cross_margins(
        80, 50, start=UsedMargin(None), end=UsedMargin(None)
    )
    assert (result.border_start, result.used_start_margin, result.used_end_margin) == (
        0, 0, -30
    )


def test_single_end_auto_can_resolve_to_negative_cross_margin():
    result = position_cross_margins(
        80, 50, start=UsedMargin(5), end=UsedMargin(None)
    )
    assert result.used_start_margin == 5
    assert result.used_end_margin == -35


def test_reverse_cross_axis_with_signed_start_margin():
    result = position_cross_margins(
        20, 100, start=UsedMargin(-5), end=UsedMargin(),
        cross_forward=False,
    )
    assert result.border_start == 85


def test_both_fixed_margins_do_not_consume_or_invent_extra_space():
    result = position_cross_margins(
        20, 100, start=UsedMargin(-4), end=UsedMargin(8)
    )
    assert (result.border_start, result.used_start_margin, result.used_end_margin) == (
        -4, -4, 8
    )


def test_invalid_cross_margin_inputs_are_rejected():
    with pytest.raises(ValueError):
        position_cross_margins(-1, 50)
    with pytest.raises(TypeError):
        position_cross_margins(20, 100, cross_forward=1)
    with pytest.raises(TypeError):
        position_cross_margins(20, 100, start=None)
