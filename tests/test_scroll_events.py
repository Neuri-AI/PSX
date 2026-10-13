"""Independent tests for scroll input normalization and nested residual routing."""
import pytest

from psx.sfle.model import Rect
from psx.sfle.native_scroll_viewport import ScrollViewportBinding
from psx.sfle.scroll_offsets import ScrollOffset
from psx.sfle.scroll_events import (
    ScrollEventTarget, dispatch_scroll_delta, scroll_key_delta,
)


def target(offset=0, *, limit=100, axis="vertical", enabled=True):
    viewport = Rect(0, 0, 100, 100)
    content = Rect(0, 0, 100 + (limit if axis == "horizontal" else 0),
                   100 + (limit if axis == "vertical" else 0))
    return ScrollEventTarget(
        ScrollViewportBinding(axis, enabled, viewport, content,
                              enabled and axis == "horizontal",
                              enabled and axis == "vertical"),
        ScrollOffset(offset if axis == "horizontal" else 0,
                     offset if axis == "vertical" else 0),
    )


def test_inner_scroll_consumes_before_ancestor():
    result = dispatch_scroll_delta(
        [target(80), target(20)], delta_y=55,
    )
    assert [(s.index, s.offset.y, s.consumed_y) for s in result.steps] == [
        (0, 100, 20), (1, 55, 35),
    ]
    assert result.remaining_y == 0


def test_exhausted_chain_reports_residual_without_double_consumption():
    result = dispatch_scroll_delta([target(100), target(90)], delta_y=45)
    assert [(s.consumed_y, s.offset.y) for s in result.steps] == [
        (0, 100), (10, 100),
    ]
    assert result.remaining_y == 35


def test_disabled_child_forwards_all_movement():
    result = dispatch_scroll_delta([target(0, enabled=False), target(0)], delta_y=36)
    assert [(s.consumed_y, s.offset.y) for s in result.steps] == [
        (0, 0), (36, 36),
    ]


def test_parent_and_child_axes_are_independent():
    result = dispatch_scroll_delta(
        [target(0, axis="horizontal"), target(0)], delta_x=18, delta_y=27,
    )
    assert result.steps[0].offset.x == 18
    assert result.steps[0].consumed_y == 0
    assert result.steps[1].offset.y == 27
    assert (result.remaining_x, result.remaining_y) == (0, 0)


def test_negative_scroll_chains_at_leading_edge():
    result = dispatch_scroll_delta([target(0), target(55)], delta_y=-30)
    assert result.steps[1].offset.y == 25
    assert result.remaining_y == 0


@pytest.mark.parametrize("key,expected", [
    ("Left", (-40, 0)), ("Right", (40, 0)),
    ("Up", (0, -40)), ("Down", (0, 40)),
    ("Page_Up", (0, -80)), ("PageDown", (0, 80)),
    ("Home", (0, -45)), ("End", (0, 75)),
])
def test_keyboard_navigation(key, expected):
    assert scroll_key_delta(key, viewport_width=120, viewport_height=80,
                            offset=ScrollOffset(0, 45), maximum_y=120) == expected


def test_invalid_delta_rejected_before_native_mutation():
    with pytest.raises(ValueError):
        dispatch_scroll_delta([target(0)], delta_y=float("nan"))
