"""F2.2.3 main-axis justify-content distribution (restricted resolved geometry)."""

from __future__ import annotations

import pytest

from psx.sfle.main_alignment import JustifyContent, resolve_main_alignment


@pytest.mark.parametrize(("mode", "leading", "between"), [
    (JustifyContent.FLEX_START, 0, 10),
    (JustifyContent.FLEX_END, 50, 10),
    (JustifyContent.CENTER, 25, 10),
    (JustifyContent.SPACE_BETWEEN, 0, 60),
    (JustifyContent.SPACE_AROUND, 12.5, 35),
    (JustifyContent.SPACE_EVENLY, 50 / 3, 10 + 50 / 3),
])
def test_main_alignment_positive_free_space(mode, leading, between):
    value = resolve_main_alignment(mode, 100, (20, 20), gap=10)
    assert value.leading_space == pytest.approx(leading)
    assert value.between_space == pytest.approx(between)
    assert value.remaining_free_space == 50


def test_center_and_end_allow_overflow_coordinates():
    center = resolve_main_alignment(JustifyContent.CENTER, 30, (40,))
    end = resolve_main_alignment(JustifyContent.FLEX_END, 30, (40,))
    assert center.leading_space == -5
    assert end.leading_space == -10


@pytest.mark.parametrize("mode", [
    JustifyContent.SPACE_BETWEEN,
    JustifyContent.SPACE_AROUND,
    JustifyContent.SPACE_EVENLY,
])
def test_distributed_alignment_overflow_falls_back_to_flex_start(mode):
    value = resolve_main_alignment(mode, 30, (40,))
    assert value.leading_space == 0


def test_signed_outer_margins_are_allowed():
    value = resolve_main_alignment(JustifyContent.FLEX_END, 100, (20, -10), gap=10)
    assert value.leading_space == 80


def test_no_items_does_not_distribute_nonexistent_spaces():
    value = resolve_main_alignment(JustifyContent.SPACE_EVENLY, 100, ())
    assert value.leading_space == 0
    assert value.remaining_free_space == 100


def test_fixed_gap_survives_distribution_fallback():
    value = resolve_main_alignment(JustifyContent.SPACE_BETWEEN, 30, (30, 30), gap=8)
    assert value.between_space == 8


def test_type_and_range_checks():
    with pytest.raises(TypeError):
        resolve_main_alignment("center", 100, (20,))
    with pytest.raises(ValueError):
        resolve_main_alignment(JustifyContent.CENTER, -1, (20,))
    with pytest.raises(ValueError):
        resolve_main_alignment(JustifyContent.CENTER, 100, (float("nan"),))
