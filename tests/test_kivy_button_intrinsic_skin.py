"""Kivy Button retains its themed skin and a single-line caption."""

import pytest


def test_kivy_button_caption_is_intrinsically_unwrapped():
    pytest.importorskip("kivy")
    from kivy.uix.button import Button
    from psx.renderers.components.button import apply_kivy_button

    button = Button(size_hint=(None, None))
    apply_kivy_button(button, {"label": "Count is 55", "font_size": 16, "enabled": True})
    button.text_size = (None, None)
    button.texture_update()
    natural_width = button.texture_size[0]
    button.size = (15, 15)
    button.texture_update()
    assert button.text_size == [None, None] or tuple(button.text_size) == (None, None)
    assert button.texture_size[0] == natural_width


def test_kivy_button_retains_native_skin_without_css_background():
    pytest.importorskip("kivy")
    from kivy.uix.button import Button
    button = Button()
    assert button.background_normal
    assert button.background_down

def test_css_styled_html_button_without_background_keeps_native_skin_and_default_padding():
    """Color-only CSS keeps native Button colors and PSX's 6 CSS-px padding."""
    pytest.importorskip("kivy")
    from psx.css.cascade import StyleTarget, resolve_style
    from psx.css.parser import parse_stylesheet
    from psx.renderers.kivy.kivy import (
        KivyHandle, KivyRenderer, _kivy_button_factory,
    )

    widget = _kivy_button_factory()
    original = (
        widget.background_normal, widget.background_down,
        tuple(widget.background_color),
    )
    handle = KivyHandle("Button", widget, {"label": "Usuarios"})
    style = resolve_style(
        parse_stylesheet("button {color:#6b7385;}"), StyleTarget("button"),
    )
    renderer = KivyRenderer()
    renderer.apply_css(handle, style)

    assert widget.background_normal == original[0]
    assert widget.background_down == original[1]
    assert tuple(widget.background_color) == original[2]
    assert not hasattr(widget, "_psx_css_button_background")
    assert widget._psx_ua_button_padding_active is True
    assert tuple(widget._psx_ua_button_padding) == (6.0, 6.0, 6.0, 6.0)
    assert all(
        abs(actual - 6.0 * renderer._psx_css_pixel_scale) < 0.01
        for actual in widget.padding
    )

    renderer.apply_css(handle, None)
    assert not hasattr(widget, "_psx_css_button_background")
    assert (
        widget.background_normal, widget.background_down,
        tuple(widget.background_color),
    ) == original
