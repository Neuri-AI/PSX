"""F2.2.2 integrated line fitting, flex targets and signed/auto margins."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.main_margins import UsedMargin
from psx.sfle.margin_flex_pipeline import (
    MarginFlexItem, compute_margin_flex_layout,
)
from psx.sfle.model import WritingDirection


def item(name: str, basis: float, start: float | None = 0, end: float | None = 0,
         *, grow: float = 0, padding: float = 0) -> MarginFlexItem:
    return MarginFlexItem(
        node_id=name,
        flex=FlexBasis(basis, basis, grow=grow, shrink=0),
        cross_content_size=10,
        edges=UsedBoxEdges(padding=UsedEdges(left=padding, right=padding)),
        main_start=UsedMargin(start),
        main_end=UsedMargin(end),
    )


def test_auto_margin_is_distributed_after_flex_growth():
    result = compute_margin_flex_layout(
        (item("a", 20, 0, None, grow=1), item("b", 20, None, 0)),
        100, 30,
    )
    boxes = result.boxes
    # The growing first item consumes all positive free space (60px).
    assert boxes[0].border.width == 80
    assert boxes[1].border.x == 80
    assert boxes[0].used_main_end_margin == 0
    assert boxes[1].used_main_start_margin == 0


def test_auto_margins_absorb_space_without_growth():
    result = compute_margin_flex_layout(
        (item("a", 20, 0, None), item("b", 20, None, 0)), 100, 30,
    )
    assert result.lines == (("a", "b"),)
    assert result.boxes[0].used_main_end_margin == 30
    assert result.boxes[1].used_main_start_margin == 30
    assert result.boxes[1].border.x == 80


def test_signed_margins_affect_wrap_before_flexing():
    result = compute_margin_flex_layout(
        (item("a", 60, -20), item("b", 60, -20)),
        90, 60, wrap=FlexWrap.WRAP,
    )
    assert result.lines == (("a", "b"),)
    assert [box.border.x for box in result.boxes] == [-20, 20]


def test_wrapping_counts_auto_as_zero():
    result = compute_margin_flex_layout(
        (item("a", 60, None), item("b", 60, None)),
        100, 60, wrap=FlexWrap.WRAP,
    )
    assert result.lines == (("a",), ("b",))


def test_rtl_signed_main_start_mapping():
    result = compute_margin_flex_layout(
        (item("a", 20, -10),), 100, 30,
        direction=FlexDirection.ROW, writing=WritingDirection.RTL,
    )
    assert result.boxes[0].border.x == 90


def test_border_and_padding_are_not_mistaken_for_signed_margins():
    result = compute_margin_flex_layout(
        (item("a", 20, -5, padding=3),), 100, 30,
    )
    box = result.boxes[0]
    assert box.border.x == -5
    assert box.border.width == 26
    assert box.content.x == -2
    assert box.content.width == 20


def test_cross_margin_not_claimed_as_supported():
    sample = item("a", 20)
    with pytest.raises(ValueError, match="physical margins"):
        replace(sample, edges=UsedBoxEdges(margin=UsedEdges(top=2)))


def test_column_reverse_autos_use_main_vertical_axis():
    result = compute_margin_flex_layout(
        (item("a", 20, None, None),), 40, 100,
        direction=FlexDirection.COLUMN_REVERSE,
    )
    assert result.boxes[0].border.y == 40
