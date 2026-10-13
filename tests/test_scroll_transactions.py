"""Native Scroll transaction regression: resize, old extents and rollback."""
from types import SimpleNamespace

from psx.sfle.native_scroll_transaction import (
    capture_scroll_hosts, restore_scroll_hosts, prior_scroll_offset,
)
from psx.sfle.scroll_offsets import ScrollOffset
from psx.sfle.native_scroll_hosts import apply_kivy_scroll
from psx.sfle.native_scroll_viewport import ScrollViewportBinding
from psx.sfle.model import Rect


class Content:
    def __init__(self, width=300, height=200):
        self.width, self.height = width, height

    @property
    def size(self):
        return (self.width, self.height)

    @size.setter
    def size(self, pair):
        self.width, self.height = pair

    def resize(self, width, height):
        self.size = (width, height)


class Bar:
    def __init__(self, value=0, maximum=200):
        self._value, self._maximum = value, maximum

    def maximum(self):
        return self._maximum

    def value(self):
        return self._value

    def setRange(self, minimum, maximum):
        self._maximum = maximum
        self._value = min(self._value, maximum)

    def setValue(self, value):
        self._value = min(max(0, value), self._maximum)


class QtHost:
    _psx_sfle_scroll = True

    def __init__(self):
        self._psx_content = Content()
        self.h, self.v = Bar(80, 200), Bar(60, 120)
        self.focus_token = object()

    def horizontalScrollBar(self):
        return self.h

    def verticalScrollBar(self):
        return self.v


def test_qt_transaction_restores_native_ranges_offsets_and_identity():
    host = QtHost()
    saved = capture_scroll_hosts("qt", {"scroll": SimpleNamespace(widget=host)})
    assert prior_scroll_offset(saved, host) == ScrollOffset(80, 60)
    focus = host.focus_token
    host._psx_content.resize(60, 30)
    host.h.setRange(0, 0)
    host.v.setRange(0, 0)
    restore_scroll_hosts(saved)
    assert host._psx_content.size == (300, 200)
    assert (host.h.value(), host.v.value()) == (80, 60)
    assert (host.h.maximum(), host.v.maximum()) == (200, 120)
    assert host.focus_token is focus


def test_kivy_reflow_retains_logical_pixels_not_stale_fractions():
    view = SimpleNamespace(
        _psx_sfle_scroll=True,
        _psx_content=Content(),
        width=100, height=80,
        scroll_x=0.5, scroll_y=0.5,
        _psx_scroll_previous_overflow=(200, 120),
    )
    view._psx_content.size_hint = (None, None)
    saved = capture_scroll_hosts("kivy", {"scroll": SimpleNamespace(widget=view)})
    previous = prior_scroll_offset(saved, view)
    assert previous == ScrollOffset(100, 60)
    binding = ScrollViewportBinding(
        "both", True, Rect(0, 0, 180, 140),
        Rect(0, 0, 300, 200), True, True,
    )
    applied = apply_kivy_scroll(view, binding, previous)
    assert applied.offset == previous
    assert abs(view.scroll_x - 100 / 120) < 1e-9
    assert view.scroll_y == 0.0
    restore_scroll_hosts(saved)
    assert view._psx_content.size == (300, 200)
    assert view.scroll_x == 0.5 and view.scroll_y == 0.5
    assert view._psx_scroll_previous_overflow == (200, 120)


def test_kivy_shrinking_content_clamps_and_failed_commit_rolls_back():
    view = SimpleNamespace(
        _psx_sfle_scroll=True, _psx_content=Content(), width=100,
        height=80, scroll_x=1.0, scroll_y=0.0,
        _psx_scroll_previous_overflow=(200, 120),
    )
    view._psx_content.size_hint = (None, None)
    saved = capture_scroll_hosts("kivy", {"scroll": SimpleNamespace(widget=view)})
    previous = prior_scroll_offset(saved, view)
    binding = ScrollViewportBinding(
        "both", True, Rect(0, 0, 100, 80),
        Rect(0, 0, 50, 40), True, True,
    )
    assert apply_kivy_scroll(view, binding, previous).offset == ScrollOffset()
    assert (view.scroll_x, view.scroll_y) == (0.0, 1.0)
    restore_scroll_hosts(saved)
    assert (view.scroll_x, view.scroll_y) == (1.0, 0.0)
