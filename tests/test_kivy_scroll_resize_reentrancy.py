"""Regression coverage for Kivy Scroll resize feedback loops."""

import pytest

pytest.importorskip("kivy")

from psx.renderers.kivy.scroll import KivyScrollAdapter


class _Content:
    minimum_width = 400.0
    minimum_height = 500.0

    def __init__(self):
        self._width = 0.0
        self._height = 0.0
        self.owner = None
        self.writes = 0

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self.writes += 1
        self._width = value
        # Simulate a native geometry/property callback synchronously
        # dispatching another content-size request.
        KivyScrollAdapter._resize_content(self.owner)

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self.writes += 1
        self._height = value
        KivyScrollAdapter._resize_content(self.owner)


class _View:
    width = 200.0
    height = 150.0
    _psx_props = {"direction": "vertical"}

    def __init__(self):
        self._psx_content = _Content()
        self._psx_content.owner = self


def test_scroll_content_resize_does_not_reenter_on_native_dispatch():
    view = _View()
    KivyScrollAdapter._resize_content(view)
    assert (view._psx_content.width, view._psx_content.height) == (200.0, 500.0)
    assert view._psx_content.writes == 2
    KivyScrollAdapter._resize_content(view)
    assert view._psx_content.writes == 2


def test_scroll_content_resize_recovers_after_dispatch_exception():
    view = _View()
    content = view._psx_content
    content.owner = view
    # A missing minimum value raises before any geometry is published.
    content.minimum_width = None
    view._psx_props = {"direction": "horizontal"}
    with pytest.raises(TypeError):
        KivyScrollAdapter._resize_content(view)
    assert view._psx_resizing_content is False
    content.minimum_width = 400.0
    KivyScrollAdapter._resize_content(view)
    assert (content.width, content.height) == (400.0, 150.0)
