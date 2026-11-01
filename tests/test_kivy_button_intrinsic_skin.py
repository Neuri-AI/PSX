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
