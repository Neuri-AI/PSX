"""Tests for the intentionally narrow integrated resolved-size Flex pipeline."""

from __future__ import annotations

import pytest

from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.model import WritingDirection
from psx.sfle.resolved_pipeline import ResolvedFlexItem, compute_resolved_flex


def node(
    name: str,
    basis: float,
    *,
    grow: float = 0.0,
    shrink: float = 1.0,
    minimum: float = 0.0,
    maximum: float | None = None,
    cross: float = 10.0,
    order: int = 0,
) -> ResolvedFlexItem:
    hypothetical = max(minimum, min(basis, maximum)) if maximum is not None else max(
        minimum, basis
    )
    return ResolvedFlexItem(
        name,
        FlexBasis(basis, hypothetical, grow, shrink, minimum, maximum),
        cross,
        order,
    )


def geometry(result):
    return {
        item.node_id: (
            item.rect.x, item.rect.y, item.rect.width, item.rect.height, item.line_index
        )
        for item in result.items
    }


def test_grow_is_resolved_before_final_positioning():
    result = compute_resolved_flex(
        (node("a", 20, grow=1), node("b", 20, grow=2)), 100, 30, main_gap=10
    )
    assert geometry(result) == {
        "a": (0, 0, pytest.approx(36.6666666667), 10, 0),
        "b": (pytest.approx(46.6666666667), 0, pytest.approx(53.3333333333), 10, 0),
    }


def test_shrink_is_weighted_by_base_size():
    result = compute_resolved_flex(
        (node("a", 100), node("b", 50)), 100, 30,
    )
    assert geometry(result) == {
        "a": (0, 0, pytest.approx(66.6666666667), 10, 0),
        "b": (pytest.approx(66.6666666667), 0, pytest.approx(33.3333333333), 10, 0),
    }


def test_wrapping_uses_hypothetical_sizes_before_flex_distribution():
    result = compute_resolved_flex(
        (node("a", 60, grow=1), node("b", 60, grow=1)),
        100, 70, wrap=FlexWrap.WRAP, cross_gap=5
    )
    assert result.lines == (("a",), ("b",))
    assert geometry(result) == {
        "a": (0, 0, 100, 10, 0),
        "b": (0, 15, 100, 10, 1),
    }


@pytest.mark.parametrize(
    ("direction", "writing", "expected"),
    [
        (FlexDirection.ROW, WritingDirection.LTR, (0, 35)),
        (FlexDirection.ROW, WritingDirection.RTL, (80, 45)),
        (FlexDirection.ROW_REVERSE, WritingDirection.LTR, (80, 45)),
        (FlexDirection.ROW_REVERSE, WritingDirection.RTL, (0, 35)),
    ],
)
def test_axes_are_preserved_after_size_resolution(direction, writing, expected):
    result = compute_resolved_flex(
        (node("a", 20), node("b", 20)),
        100, 30, direction=direction, writing=writing, main_gap=15,
    )
    assert tuple(item.rect.x for item in result.items) == expected


def test_order_controls_lines_and_placement_without_mutating_input():
    items = (node("a", 60, order=1), node("b", 50, order=0), node("c", 40, order=1))
    result = compute_resolved_flex(items, 100, 30, wrap=FlexWrap.WRAP, main_gap=10)
    assert result.lines == (("b",), ("a", "c"))
    assert tuple(item.node_id for item in items) == ("a", "b", "c")


def test_max_clamp_freezes_first_item_and_reallocates_remaining_space():
    result = compute_resolved_flex(
        (node("a", 20, grow=1, maximum=30), node("b", 20, grow=1)),
        100, 30,
    )
    assert tuple(item.rect.width for item in result.items) == (30, 70)


def test_empty_and_invalid_inputs():
    assert compute_resolved_flex((), 100, 100).items == ()
    with pytest.raises(ValueError):
        compute_resolved_flex((node("a", 10), node("a", 20)), 100, 100)
    with pytest.raises(ValueError):
        compute_resolved_flex((node("a", 10),), 100, 100, main_gap=-1)
    with pytest.raises(TypeError):
        ResolvedFlexItem("x", node("a", 10).flex, 10, order=1.0)
