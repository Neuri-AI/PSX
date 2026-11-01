"""Default Kivy Button UA padding is accounted for by Cinnamon."""

import pytest


def test_button_default_padding_contributes_to_intrinsic_size():
    pytest.importorskip("kivy")
    from psx.renderers.kivy.kivy import _kivy_button_factory
    from psx.sfle.kivy_measurement import KivyMeasurementSource
    from psx.sfle.measurement_plan import MeasurementRequest
    from psx.sfle.model import LayoutConstraints, AvailableSize

    widget = _kivy_button_factory()
    widget.text = "Count is 0"
    widget.padding = (6, 6, 6, 6)
    widget.text_size = (None, None)
    widget.texture_update()
    source = KivyMeasurementSource({"button": widget})
    request = MeasurementRequest(
        "button",
        LayoutConstraints(AvailableSize(320, True), AvailableSize(None, False)),
        1, 1,
    )
    intrinsic = source.measure(request).intrinsic
    assert intrinsic.preferred_width == widget.texture_size[0] + 12
    assert intrinsic.preferred_height == widget.texture_size[1] + 12

    # Explicit CSS padding belongs to Cinnamon, not native intrinsic size.
    widget._psx_ua_button_padding_active = False
    overridden = source.measure(request).intrinsic
    assert overridden.preferred_width == widget.texture_size[0]
    assert overridden.preferred_height == widget.texture_size[1]
