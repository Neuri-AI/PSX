"""Native CSS border widths on Kivy/SDL Retina and standard displays."""

from __future__ import annotations

import pytest

pytest.importorskip("kivy")

from kivy.uix.button import Button
from kivy.uix.widget import Widget

from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet
from psx.renderers.kivy.kivy import KivyHandle, KivyRenderer


def _style(css, selector="div"):
    return resolve_style(
        parse_stylesheet(selector + " {" + css + "}"),
        StyleTarget(selector),
    )


@pytest.mark.parametrize("scale", (1.0, 2.0))
@pytest.mark.parametrize("kind", ("div", "Button"))
def test_single_css_pixel_border_uses_exact_native_drawable_width(scale, kind):
    """Line triangulation paints twice its width, so factor must be 0.5."""
    renderer = KivyRenderer()
    renderer._psx_css_pixel_scale = scale
    widget = Widget() if kind == "div" else Button()
    widget.size = (240 * scale, 80 * scale)
    handle = KivyHandle(kind, widget, {})
    style = _style("border: 1px solid #e0e0e0; border-radius: 8px")
    renderer.apply_css(handle, style)
    group, redraw, color, line = (
        widget._psx_css_stroke if kind == "div"
        else widget._psx_css_control_stroke
    )
    assert line.force_custom_drawing_method is True
    assert line.width == pytest.approx(scale / 2)
    assert tuple(color.rgba) == pytest.approx((224 / 255,) * 3 + (1.0,))
    assert not hasattr(widget, "_psx_css_side_strokes")
    assert not hasattr(widget, "_psx_css_control_side_strokes")
    widget.size = (300 * scale, 110 * scale)
    assert line.width == pytest.approx(scale / 2)

    renderer.apply_css(handle, _style("border: 2px solid #e0e0e0"))
    assert line.width == pytest.approx(scale)
    renderer.apply_css(handle, None)
    assert not hasattr(widget, "_psx_css_stroke")
    assert not hasattr(widget, "_psx_css_control_stroke")


@pytest.mark.parametrize("scale", (1.0, 2.0))
@pytest.mark.parametrize("kind", ("div", "Button"))
def test_one_pixel_side_border_uses_same_retina_raster_policy(scale, kind):
    renderer = KivyRenderer()
    renderer._psx_css_pixel_scale = scale
    widget = Widget() if kind == "div" else Button()
    widget.size = (200 * scale, 80 * scale)
    handle = KivyHandle(kind, widget, {})
    style = _style(
        "border-bottom-width: 1px; border-bottom-color: #e0e0e0; "
        "border-radius: 8px"
    )
    renderer.apply_css(handle, style)
    group, redraw, sides, lines = (
        widget._psx_css_side_strokes if kind == "div"
        else widget._psx_css_control_side_strokes
    )
    assert len(lines) == 1
    assert sides[0][0] == "bottom"
    assert lines[0][2].force_custom_drawing_method is True
    assert lines[0][2].width == pytest.approx(scale / 2)
    assert not hasattr(widget, "_psx_css_stroke")
    assert not hasattr(widget, "_psx_css_control_stroke")
    renderer.apply_css(handle, None)
    assert not hasattr(widget, "_psx_css_side_strokes")
    assert not hasattr(widget, "_psx_css_control_side_strokes")



@pytest.mark.parametrize("kind", ("div", "Button"))
def test_authored_css_cursor_reaches_renderer_and_releases_window_binding(kind):
    renderer = KivyRenderer()
    widget = Widget() if kind == "div" else Button()
    handle = KivyHandle(kind, widget, {})
    renderer.apply_css(handle, _style("cursor: pointer"))
    manager = renderer._psx_css_cursor_manager
    assert manager.styles[widget] == "pointer"
    renderer.apply_css(handle, _style("cursor: default"))
    assert manager.styles[widget] == "default"
    renderer.apply_css(handle, _style("cursor: auto"))
    assert widget not in manager.styles
    renderer.apply_css(handle, _style("cursor: pointer"))
    assert manager.styles[widget] == "pointer"
    renderer.apply_css(handle, None)
    assert widget not in manager.styles
    assert manager._bound is False
