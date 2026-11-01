"""Regression for nested Kivy Flex baseline measurements."""

import pytest


def test_width_dependent_text_retains_baseline():
    pytest.importorskip("kivy")
    from kivy.uix.label import Label
    from psx.sfle.kivy_measurement import KivyMeasurementSource

    text = Label(text="Hello world", size_hint=(None, None))
    text.texture_update()
    source = KivyMeasurementSource({"text": text})
    result = source.measure_width("text", 120.0)
    assert result.baseline is not None
    assert result.baseline == result.preferred_height


def test_link_native_measurement_has_baseline():
    pytest.importorskip("kivy")
    from kivy.uix.button import Button
    from psx.sfle.kivy_measurement import KivyMeasurementSource
    from psx.sfle.measurement_plan import MeasurementRequest
    from psx.sfle.model import AvailableSize, LayoutConstraints

    widget = Button(text="Explore docs", size_hint=(None, None))
    widget.texture_update()
    widget._psx_sfle_link = True
    constraints = LayoutConstraints(
        AvailableSize(320, True), AvailableSize(None, False)
    )
    source = KivyMeasurementSource({"link": widget})
    result = source.measure(MeasurementRequest("link", constraints, 1, 1))
    assert result.intrinsic.baseline == result.intrinsic.preferred_height
