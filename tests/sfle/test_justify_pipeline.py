"""F2.2.3 direction-aware justify-content integration in resolved Flex geometry."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection
from psx.sfle.main_alignment import JustifyContent
from psx.sfle.main_margins import UsedMargin
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout
from psx.sfle.model import WritingDirection


def item(name: str, *, start: float | None = 0,
         end: float | None = 0, grow: float = 0) -> MarginFlexItem:
    return MarginFlexItem(
        node_id=name,
        flex=FlexBasis(20, 20, grow=grow, shrink=0),
        cross_content_size=10,
        main_start=UsedMargin(start),
        main_end=UsedMargin(end),
    )


@pytest.mark.parametrize(("justify", "expected"), [
    (JustifyContent.FLEX_START, (0, 30)),
    (JustifyContent.FLEX_END, (50, 80)),
    (JustifyContent.CENTER, (25, 55)),
    (JustifyContent.SPACE_BETWEEN, (0, 80)),
    (JustifyContent.SPACE_AROUND, (12.5, 67.5)),
    (JustifyContent.SPACE_EVENLY, (50 / 3, 30 + 100 / 3)),
])
def test_justify_controls_used_border_coordinates(justify, expected):
    result = compute_margin_flex_layout(
        (item("a"), item("b")), 100, 40, main_gap=10, justify=justify,
    )
    assert tuple(box.border.x for box in result.boxes) == pytest.approx(expected)


@pytest.mark.parametrize(("direction", "writing", "expected"), [
    (FlexDirection.ROW, WritingDirection.RTL, (80, 0)),
    (FlexDirection.ROW_REVERSE, WritingDirection.LTR, (80, 0)),
    (FlexDirection.ROW_REVERSE, WritingDirection.RTL, (0, 80)),
])
def test_space_between_maps_logical_main_to_physical_coordinates(
    direction, writing, expected,
):
    result = compute_margin_flex_layout(
        (item("a"), item("b")), 100, 40,
        direction=direction, writing=writing, main_gap=10,
        justify=JustifyContent.SPACE_BETWEEN,
    )
    assert tuple(box.border.x for box in result.boxes) == expected


def test_column_center_positions_main_axis_y():
    result = compute_margin_flex_layout(
        (item("a"),), 40, 100, direction=FlexDirection.COLUMN,
        justify=JustifyContent.CENTER,
    )
    assert result.boxes[0].border.y == 40


def test_auto_margin_consumes_positive_space_before_justify():
    result = compute_margin_flex_layout(
        (item("a", end=None), item("b")), 100, 40,
        justify=JustifyContent.FLEX_END,
    )
    assert tuple(box.border.x for box in result.boxes) == (0, 80)
    assert result.boxes[0].used_main_end_margin == 60


def test_flex_grow_consumes_free_space_before_justify():
    result = compute_margin_flex_layout(
        (item("a", grow=1), item("b")), 100, 40,
        justify=JustifyContent.CENTER,
    )
    assert tuple(box.border.x for box in result.boxes) == (0, 80)


def test_signed_margin_and_flex_end_preserve_overflow():
    value = replace(item("a"), main_start=UsedMargin(-10))
    result = compute_margin_flex_layout(
        (value,), 100, 40, justify=JustifyContent.FLEX_END,
    )
    assert result.boxes[0].border.x == 80


def test_invalid_justify_is_rejected():
    with pytest.raises(TypeError):
        compute_margin_flex_layout((item("a"),), 100, 40, justify="center")
