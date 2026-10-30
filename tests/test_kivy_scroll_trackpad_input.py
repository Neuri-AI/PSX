"""Kivy trackpad ownership inside a Cinnamon Grid/Scroll viewport."""

import pytest

pytest.importorskip("kivy")

from types import SimpleNamespace

from kivy.uix.scrollview import ScrollView
from psx.renderers.kivy.scroll import KivyScrollAdapter, _PSXScrollView


def test_trackpad_and_touch_handlers_are_owned_by_native_scrollview():
    # Kivy 2.3.1 implements on_scroll_start/on_scroll_move/on_scroll_stop as
    # one touch lifecycle. An adapter that partially reimplements gestures
    # can process the same trackpad delta twice and recursively dispatch.
    assert _PSXScrollView.on_touch_down is ScrollView.on_touch_down
    assert _PSXScrollView.on_touch_move is ScrollView.on_touch_move
    assert _PSXScrollView.on_touch_up is ScrollView.on_touch_up
    assert _PSXScrollView.on_scroll_start is ScrollView.on_scroll_start
    assert _PSXScrollView.on_scroll_move is ScrollView.on_scroll_move
    assert _PSXScrollView.on_scroll_stop is ScrollView.on_scroll_stop


def test_cinnamon_scroll_view_disables_empty_viewport_overscroll():
    renderer = SimpleNamespace(_sfle_constraints=object())
    node = SimpleNamespace(props={})
    handle = KivyScrollAdapter().create(renderer, node, None)
    view = handle.widget
    assert view._psx_sfle_scroll is True
    assert view.always_overscroll is False
    assert view._psx_content.parent is view
    assert tuple(view._psx_content.size_hint) == (None, None)
    KivyScrollAdapter().destroy(renderer, handle)
