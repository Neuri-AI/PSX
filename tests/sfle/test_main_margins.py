"""Resolved Flexbox main-axis margin distribution in logical source order."""

from __future__ import annotations

import pytest

from psx.sfle.line_layout import FlexDirection
from psx.sfle.main_margins import (
    MarginItem, UsedMargin, position_main_margins,
)
from psx.sfle.model import WritingDirection


def item(name: str, start: float | None = 0, end: float | None = 0):
    return MarginItem(name, 20, UsedMargin(start), UsedMargin(end))


def test_positive_free_space_is_shared_across_auto_margin_edges():
    out = position_main_margins((item("a", 0, None), item("b", None, 0)), 100)
    assert [p.border_start for p in out] == [0, 80]
    assert [p.used_end_margin for p in out] == [30, 0]
    assert [p.used_start_margin for p in out] == [0, 30]


def test_single_item_two_auto_margins_centers_border_box():
    out = position_main_margins((item("a", None, None),), 100)
    assert out[0].border_start == 40
    assert out[0].used_start_margin == out[0].used_end_margin == 40


def test_negative_free_space_auto_margins_use_zero():
    out = position_main_margins((item("a", None, None),), 10)
    assert (out[0].border_start, out[0].used_start_margin, out[0].used_end_margin) == (0, 0, 0)


def test_signed_margin_offsets_border_box_without_negative_rectangle():
    out = position_main_margins((item("a", -15, 0),), 100)
    assert out[0].border_start == -15
    assert out[0].border_main_size == 20


@pytest.mark.parametrize(
    ("direction", "writing", "expected"),
    [
        (FlexDirection.ROW, WritingDirection.LTR, (-15, 15)),
        (FlexDirection.ROW, WritingDirection.RTL, (95, 65)),
        (FlexDirection.ROW_REVERSE, WritingDirection.LTR, (95, 65)),
        (FlexDirection.ROW_REVERSE, WritingDirection.RTL, (-15, 15)),
        (FlexDirection.COLUMN_REVERSE, WritingDirection.LTR, (95, 65)),
    ],
)
def test_reverse_and_rtl_axes_with_negative_margin(direction, writing, expected):
    out = position_main_margins(
        (item("a", -15, 0), item("b", 0, 0)), 100,
        main_gap=10, direction=direction, writing=writing,
    )
    assert tuple(p.border_start for p in out) == expected


def test_reject_duplicate_ids_nonfinite_margins_and_negative_extents():
    with pytest.raises(ValueError):
        position_main_margins((item("a"), item("a")), 100)
    with pytest.raises(ValueError):
        UsedMargin(float("inf"))
    with pytest.raises(ValueError):
        position_main_margins((item("a"),), -1)
