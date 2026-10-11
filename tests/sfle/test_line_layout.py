"""Behavior-focused coverage for the F2.2 resolved-line layout kernel."""

from __future__ import annotations

import pytest

from psx.sfle.line_layout import (
    FlexDirection, FlexWrap, ResolvedItem, form_flex_lines, place_resolved_lines,
)
from psx.sfle.model import WritingDirection


def item(name: str, main: float, cross: float = 10, order: int = 0) -> ResolvedItem:
    return ResolvedItem(name, main, cross, order)


@pytest.mark.parametrize(
    ("direction", "writing", "expected"),
    [
        (FlexDirection.ROW, WritingDirection.LTR, ((0, 0), (35, 0))),
        (FlexDirection.ROW, WritingDirection.RTL, ((80, 0), (45, 0))),
        (FlexDirection.ROW_REVERSE, WritingDirection.LTR, ((80, 0), (45, 0))),
        (FlexDirection.ROW_REVERSE, WritingDirection.RTL, ((0, 0), (35, 0))),
        (FlexDirection.COLUMN, WritingDirection.LTR, ((0, 0), (0, 35))),
        (FlexDirection.COLUMN, WritingDirection.RTL, ((90, 0), (90, 35))),
        (FlexDirection.COLUMN_REVERSE, WritingDirection.LTR, ((0, 80), (0, 45))),
        (FlexDirection.COLUMN_REVERSE, WritingDirection.RTL, ((90, 80), (90, 45))),
    ],
)
def test_main_axes_and_writing_direction(direction, writing, expected):
    lines = form_flex_lines((item("a", 20), item("b", 20)), 100, 15)
    result = place_resolved_lines(
        lines, 100, 100, direction=direction, writing=writing, main_gap=15
    )
    assert tuple((p.rect.x, p.rect.y) for p in result.items) == expected
    assert result.lines == (("a", "b"),)


def test_line_breaks_before_shrink_and_preserves_oversize_items():
    lines = form_flex_lines(
        (item("a", 40), item("b", 40), item("c", 120), item("d", 30)),
        100, 10, FlexWrap.WRAP
    )
    assert tuple(tuple(i.node_id for i in line) for line in lines) == (
        ("a", "b"), ("c",), ("d",),
    )


def test_order_is_stable_without_mutating_source():
    source = (item("a", 20, order=1), item("b", 20, order=0), item("c", 20, order=1))
    lines = form_flex_lines(source, 200)
    assert tuple(v.node_id for v in lines[0]) == ("b", "a", "c")
    assert tuple(v.node_id for v in source) == ("a", "b", "c")


def test_cross_wrap_reverse_inverts_line_stack():
    lines = form_flex_lines(
        (item("a", 60, 20), item("b", 60, 30)),
        100, wrap=FlexWrap.WRAP_REVERSE
    )
    placed = place_resolved_lines(
        lines, 100, 100, wrap=FlexWrap.WRAP_REVERSE, cross_gap=10
    )
    assert tuple((p.rect.x, p.rect.y) for p in placed.items) == ((0, 80), (0, 40))


def test_cross_axis_is_right_to_left_for_rtl_columns():
    lines = form_flex_lines(
        (item("a", 50, 15), item("b", 50, 20)),
        50, wrap=FlexWrap.WRAP
    )
    placed = place_resolved_lines(
        lines, 100, 100, direction=FlexDirection.COLUMN,
        writing=WritingDirection.RTL, wrap=FlexWrap.WRAP, cross_gap=5
    )
    assert tuple((p.rect.x, p.rect.y) for p in placed.items) == ((85, 0), (60, 0))


def test_oversize_line_is_not_silently_shrunk():
    lines = form_flex_lines((item("oversize", 120),), 100, wrap=FlexWrap.WRAP)
    result = place_resolved_lines(lines, 100, 100)
    assert result.items[0].rect.width == 120


def test_nonfinite_ambiguous_or_negative_inputs_are_rejected():
    with pytest.raises((TypeError, ValueError)):
        ResolvedItem("a", float("nan"), 10)
    with pytest.raises(ValueError):
        form_flex_lines((item("a", 10), item("a", 20)), 100)
    with pytest.raises(ValueError):
        form_flex_lines((item("a", 10),), 100, main_gap=-1)
    with pytest.raises(TypeError):
        form_flex_lines((item("a", 10, order=1.0),), 100)


def test_nowrap_rejects_multiple_explicit_lines():
    with pytest.raises(ValueError):
        place_resolved_lines(
            ((item("a", 10),), (item("b", 10),)),
            100, 100, wrap=FlexWrap.NOWRAP,
        )
