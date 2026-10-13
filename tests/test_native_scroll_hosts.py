"""Native scroll host projection contracts with observable toolkit-shaped ports."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from psx.sfle.model import Rect
from psx.sfle.native_scroll_viewport import ScrollViewportBinding
from psx.sfle.scroll_offsets import ScrollOffset
from psx.sfle.native_scroll_hosts import (
    apply_headless_scroll, apply_kivy_scroll, apply_qt_scroll,
    apply_tk_scroll, host_geometry,
)


def binding(direction="both", enabled=True):
    x = enabled and direction in ("horizontal", "both")
    y = enabled and direction in ("vertical", "both")
    return ScrollViewportBinding(direction, enabled, Rect(0, 0, 100, 80),
                                 Rect(0, 0, 300, 200), x, y)


class Bar:
    def __init__(self):
        self.value = None

    def setValue(self, value):
        self.value = value


class QtContent:
    def resize(self, x, y):
        self.size = (x, y)


class QtArea:
    def __init__(self):
        self._psx_content = QtContent()
        self.h = Bar()
        self.v = Bar()

    def horizontalScrollBar(self):
        return self.h

    def verticalScrollBar(self):
        return self.v


class Canvas:
    def __init__(self):
        self.configuration = {}
        self.window = {}
        self.offsets = {}

    def itemconfigure(self, item, **kwargs):
        self.window[item] = kwargs

    def configure(self, **kwargs):
        self.configuration.update(kwargs)

    def xview_moveto(self, fraction):
        self.offsets["x"] = fraction

    def yview_moveto(self, fraction):
        self.offsets["y"] = fraction


@pytest.mark.parametrize("direction,expected", [
    ("both", (200, 120)),
    ("horizontal", (200, 0)),
    ("vertical", (0, 120)),
])
def test_native_ports_respect_axis_limits(direction, expected):
    b = binding(direction)
    original = b.content
    requested = ScrollOffset(500, 500)
    q = QtArea()
    t = SimpleNamespace(_psx_canvas=Canvas(), _psx_window=7)
    k = SimpleNamespace(_psx_content=SimpleNamespace(size_hint=(1, 1)))
    qt = apply_qt_scroll(q, b, requested)
    tk = apply_tk_scroll(t, b, requested)
    kivy = apply_kivy_scroll(k, b, requested)
    headless = apply_headless_scroll(b, requested)
    assert all(result.offset == ScrollOffset(*expected)
               for result in (qt, tk, kivy, headless))
    assert q._psx_content.size == (300, 200)
    assert (q.h.value, q.v.value) == expected
    assert t._psx_canvas.window[7] == {"width": 300, "height": 200}
    assert t._psx_canvas.configuration["scrollregion"] == (0, 0, 300, 200)
    assert t._psx_canvas.offsets == {"x": expected[0] / 300,
                                     "y": expected[1] / 200}
    assert k._psx_content.size == (300, 200)
    assert k._psx_content.size_hint == (None, None)
    assert k.scroll_x == (expected[0] / 200 if direction != "vertical" else 0)
    assert k.scroll_y == (1 - expected[1] / 120 if direction != "horizontal" else 1)
    assert b.content is original


def test_disabled_scroll_resets_offsets_on_every_port():
    b = binding(enabled=False)
    qt = QtArea()
    t = SimpleNamespace(_psx_canvas=Canvas(), _psx_window=3)
    k = SimpleNamespace(_psx_content=SimpleNamespace())
    assert apply_qt_scroll(qt, b, ScrollOffset(10, 20)).offset == ScrollOffset()
    assert apply_tk_scroll(t, b, ScrollOffset(10, 20)).offset == ScrollOffset()
    assert apply_kivy_scroll(k, b, ScrollOffset(10, 20)).offset == ScrollOffset()
    assert (qt.h.value, qt.v.value) == (0, 0)
    assert (k.scroll_x, k.scroll_y) == (0, 1)


def test_extent_shrink_removes_both_native_offsets():
    b = ScrollViewportBinding("both", True, Rect(0, 0, 100, 80),
                              Rect(0, 0, 40, 30), True, True)
    assert host_geometry(b, ScrollOffset(20, 40)).offset == ScrollOffset()
    assert b.viewport == Rect(0, 0, 100, 80)
