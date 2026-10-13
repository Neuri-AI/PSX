"""Deterministic scroll offset acceptance, independent of native toolkit APIs."""
import math

import pytest

from psx.sfle.model import Rect
from psx.sfle.native_scroll_viewport import ScrollViewportBinding
from psx.sfle.scroll_offsets import (
    ScrollOffset, clamp_scroll_offset, consume_scroll_delta,
    content_to_viewport, viewport_to_content,
)


def binding(*, direction="both", enabled=True, viewport=(10, 20, 100, 80),
            content=(0, 0, 300, 200)):
    x, y = (direction in ("horizontal", "both"), direction in ("vertical", "both"))
    return ScrollViewportBinding(direction, enabled, Rect(*viewport),
                                 Rect(*content), x and enabled, y and enabled)


def test_scroll_offset_clamps_each_axis_and_preserves_engine_boxes():
    b = binding()
    original_viewport, original_content = b.viewport, b.content
    assert clamp_scroll_offset(b, ScrollOffset(-30, 1000)) == ScrollOffset(0, 120)
    assert clamp_scroll_offset(b, ScrollOffset(1000, 1000)) == ScrollOffset(200, 120)
    assert b.viewport is original_viewport and b.content is original_content
    assert b.content == Rect(0, 0, 300, 200)


@pytest.mark.parametrize("direction,expected", [
    ("horizontal", ScrollOffset(200, 0)),
    ("vertical", ScrollOffset(0, 120)),
    ("both", ScrollOffset(200, 120)),
])
def test_scroll_axes_are_independent(direction, expected):
    assert clamp_scroll_offset(binding(direction=direction),
                               ScrollOffset(500, 500)) == expected


def test_disabled_scroll_consumes_nothing_and_returns_event_to_parent():
    b = binding(enabled=False)
    r = consume_scroll_delta(b, ScrollOffset(12, 34), delta_x=40, delta_y=-30)
    assert r.offset == ScrollOffset()
    assert (r.remaining_x, r.remaining_y) == (40, -30)


def test_delta_consumes_only_available_extent_and_returns_residual():
    b = binding()
    r = consume_scroll_delta(b, ScrollOffset(190, 115), delta_x=25, delta_y=15)
    assert r.offset == ScrollOffset(200, 120)
    assert (r.remaining_x, r.remaining_y) == (15, 10)
    reverse = consume_scroll_delta(b, ScrollOffset(), delta_x=-15, delta_y=-5)
    assert reverse.offset == ScrollOffset()
    assert (reverse.remaining_x, reverse.remaining_y) == (-15, -5)


def test_resize_restores_valid_position_without_changing_layout():
    old = binding()
    position = clamp_scroll_offset(old, ScrollOffset(180, 100))
    resized = binding(viewport=(10, 20, 280, 180))
    assert clamp_scroll_offset(resized, position) == ScrollOffset(20, 20)
    assert position == ScrollOffset(180, 100)


def test_projection_roundtrip_and_parent_relative_translation():
    b = binding()
    offset = ScrollOffset(70, 50)
    position = content_to_viewport(b, offset, x=130, y=90)
    assert position == (70, 60)
    assert viewport_to_content(b, offset, x=position[0], y=position[1]) == (130, 90)


def test_nested_scroll_frames_keep_offsets_independent():
    outer = binding(viewport=(10, 20, 100, 80), content=(0, 0, 300, 200))
    inner = binding(viewport=(20, 30, 60, 40), content=(0, 0, 140, 100))
    inner_point = content_to_viewport(inner, ScrollOffset(12, 20), x=40, y=35)
    outer_point = content_to_viewport(outer, ScrollOffset(60, 30),
                                      x=inner_point[0], y=inner_point[1])
    assert outer_point == (18, 35)
    assert outer.content == Rect(0, 0, 300, 200)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_offsets_deltas_and_positions_fail_closed(bad):
    b = binding()
    with pytest.raises(ValueError):
        ScrollOffset(bad, 0)
    with pytest.raises(ValueError):
        consume_scroll_delta(b, ScrollOffset(), delta_y=bad)
    with pytest.raises(ValueError):
        content_to_viewport(b, ScrollOffset(), x=bad, y=0)
    with pytest.raises(ValueError):
        viewport_to_content(b, ScrollOffset(), x=0, y=bad)
