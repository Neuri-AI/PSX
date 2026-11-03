"""Kivy trackpad ownership inside a Cinnamon Grid/Scroll viewport."""

import pytest

pytest.importorskip("kivy")

from types import SimpleNamespace

from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from kivy.effects.dampedscroll import DampedScrollEffect
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
    assert isinstance(view.effect_y, ScrollEffect)
    assert not isinstance(view.effect_y, DampedScrollEffect)
    # Horizontal kinetics are unchanged; this fix targets Y-only rebound.
    assert isinstance(view.effect_x, DampedScrollEffect)
    assert view._psx_content.parent is view
    assert tuple(view._psx_content.size_hint) == (None, None)
    KivyScrollAdapter().destroy(renderer, handle)


def test_vertical_effect_clamps_on_shrinking_resize_bounds():
    """The same scroll position must not spring past changing viewport limits."""
    effect = ScrollEffect()
    effect.min = -500
    effect.max = 0
    effect.value = -350
    assert effect.value == -350

    # A taller window reduces the scrollable extent. A damped effect leaves
    # the old displacement outside bounds and springs back over later frames.
    effect.min = -180
    # A changed effect value dispatches on_value; assigning the unchanged
    # value is a no-op in Kivy's NumericProperty implementation.
    effect.value = -351
    assert effect.value == -180
    assert effect.scroll == -180
    assert effect.velocity == 0


def test_unmanaged_scroll_retains_default_vertical_effect():
    renderer = SimpleNamespace(_sfle_constraints=None)
    node = SimpleNamespace(props={})
    adapter = KivyScrollAdapter()
    handle = adapter.create(renderer, node, None)
    try:
        assert isinstance(handle.widget.effect_y, DampedScrollEffect)
    finally:
        adapter.destroy(renderer, handle)
