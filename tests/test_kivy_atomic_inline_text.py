"""Kivy should not wrap each measured word inside a mixed HTML paragraph."""

import pytest


def test_atomic_inline_text_ignores_widget_resizes():
    pytest.importorskip("kivy")
    from kivy.uix.label import Label
    from psx.renderers.components.text import size_kivy_text

    label = Label(text="main.py", size_hint=(None, None))
    label._psx_sfle_inline_atomic = True
    label.texture_update()
    natural = tuple(label.texture_size)
    label.size = (2, 5)
    size_kivy_text(label, label.size)
    label.texture_update()
    assert tuple(label.text_size) == (None, None)
    assert tuple(label.texture_size) == natural


def test_normal_text_keeps_native_wrapping():
    pytest.importorskip("kivy")
    from kivy.uix.label import Label
    from psx.renderers.components.text import size_kivy_text

    label = Label(text="this can wrap", size_hint=(None, None))
    size_kivy_text(label, (40, 20))
    assert tuple(label.text_size) == (40, 20)
