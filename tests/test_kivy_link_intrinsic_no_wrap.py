"""Kivy links keep the full intrinsic label width under centered parents."""

import pytest


def test_kivy_link_texture_remains_unwrapped_after_update():
    pytest.importorskip("kivy")
    from kivy.uix.button import Button
    from psx.renderers.kivy.link import KivyLinkAdapter

    widget = Button(markup=True, size_hint=(None, None))
    props = {
        "label": "Explore the docs", "color": "#ffffff",
        "underline": True, "enabled": True,
    }
    widget._psx_sfle_link = True
    widget.text_size = (20, None)
    KivyLinkAdapter._apply(widget, props)
    assert tuple(widget.text_size) == (None, None)
    assert widget.texture_size[0] > 20
    assert widget.texture_size[1] > 0
    widget.size = (25, 10)
    KivyLinkAdapter._apply(widget, props)
    assert tuple(widget.text_size) == (None, None)
