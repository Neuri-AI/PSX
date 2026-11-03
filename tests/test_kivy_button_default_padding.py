"""Default Kivy Button UA padding is accounted for by Cinnamon."""

import pytest


def test_button_default_padding_contributes_to_intrinsic_size():
    pytest.importorskip("kivy")
    from psx.renderers.kivy.kivy import _kivy_button_factory
    from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource
    from psx.layout.fallback.measurement_plan import MeasurementRequest
    from psx.layout.contracts.model import LayoutConstraints, AvailableSize

    widget = _kivy_button_factory()
    widget.text = "Count is 0"
    # This must be true immediately after construction, not because the
    # test injected its own padding into a widget with missing defaults.
    assert tuple(widget.padding) == (6, 6, 6, 6)
    assert widget._psx_ua_button_padding_active
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


def test_button_ignores_previous_wrapped_texture_when_measuring_natural_width():
    """A CSS text-align constraint cannot make a Kivy button measure as 'Cou/nt'."""
    pytest.importorskip("kivy")
    from psx.renderers.kivy.kivy import _kivy_button_factory
    from psx.renderers.components.button import apply_kivy_button
    from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource
    from psx.layout.fallback.measurement_plan import MeasurementRequest
    from psx.layout.contracts.model import LayoutConstraints, AvailableSize

    widget = _kivy_button_factory()
    apply_kivy_button(widget, {"label": "Count is 0", "font_size": 16})
    widget.text_size = (None, None)
    widget.texture_update()
    natural_width, natural_height = widget.texture_size
    assert natural_width > 40

    # Reproduce the stale CSS/previous-geometry text_size that splits the
    # button into several lines. This is paint state, not intrinsic content.
    widget.text_size = (36, None)
    widget.texture_update()
    constrained_texture = tuple(widget.texture_size)
    assert constrained_texture[0] <= 36 + 1

    source = KivyMeasurementSource({"button": widget})
    request = MeasurementRequest(
        "button",
        LayoutConstraints(AvailableSize(800, True), AvailableSize(400, True)),
        1, 1,
    )
    intrinsic = source.measure(request).intrinsic
    assert abs(intrinsic.preferred_width - (natural_width + 12)) <= 1
    assert abs(intrinsic.preferred_height - (natural_height + 12)) <= 1
    # Measuring must not silently remove authored text-align or resize state.
    assert tuple(widget.text_size) == (36, None)
    assert widget.background_normal and widget.background_down
    assert tuple(widget.padding) == (6, 6, 6, 6)


def test_css_center_aligned_button_retains_natural_intrinsic_width():
    """The align-resize callback must not feed wrapped text into SFLE sizing."""
    pytest.importorskip("kivy")
    from psx.css.cascade import StyleTarget, resolve_style
    from psx.css.parser import parse_stylesheet
    from psx.renderers.kivy.kivy import (
        KivyHandle, KivyRenderer, _kivy_button_factory,
    )
    from psx.renderers.components.button import apply_kivy_button
    from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource
    from psx.layout.fallback.measurement_plan import MeasurementRequest
    from psx.layout.contracts.model import LayoutConstraints, AvailableSize

    renderer = KivyRenderer()
    widget = _kivy_button_factory()
    props = {"label": "Count is 0", "font_size": 16}
    apply_kivy_button(widget, props)
    handle = KivyHandle("Button", widget, props)
    style = resolve_style(
        parse_stylesheet("button { text-align:center; }"),
        StyleTarget("button"),
    )
    renderer.apply_css(handle, style)
    widget.size = (44, 80)
    assert widget.text_size[0] < 44

    unwrapped = tuple(widget.text_size)
    widget.text_size = (None, None)
    widget.texture_update()
    natural_width = widget.texture_size[0]
    widget.text_size = unwrapped
    widget.texture_update()

    source = KivyMeasurementSource({"button": widget})
    request = MeasurementRequest(
        "button",
        LayoutConstraints(AvailableSize(800, True), AvailableSize(400, True)),
        1, 1,
    )
    intrinsic = source.measure(request).intrinsic
    assert intrinsic.min_content_width >= natural_width + 12 - 1
    assert intrinsic.preferred_width >= natural_width + 12 - 1
    assert tuple(widget.text_size) == unwrapped
    assert widget.background_normal
