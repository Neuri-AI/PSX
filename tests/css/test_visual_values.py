import pytest

from psx.css.visual_values import CssColor, VISUAL_EFFECTS, normalize_visual_value
from psx.sfle.lengths import Length


def test_background_and_text_colors():
    assert normalize_visual_value("background-color", "#F80") == CssColor("#f80")
    assert normalize_visual_value("color", "#aabbccdd") == CssColor("#aabbccdd")


def test_font_properties_and_measurement_effect():
    assert normalize_visual_value("font-family", "Inter, Arial") == "Inter, Arial"
    assert normalize_visual_value("font-weight", "bold") == 700
    assert normalize_visual_value("font-size", "18px") == Length.px(18)
    assert VISUAL_EFFECTS["font-size"] == "measurement"
    assert VISUAL_EFFECTS["background-color"] == "paint"


@pytest.mark.parametrize("name,value", [
    ("background-color", "red"),
    ("font-size", "-1px"),
    ("font-family", "url(javascript:bad)"),
    ("font-weight", "650"),
    ("text-align", "unknown"),
    ("background-image", "url(image.png)"),
])
def test_unsupported_visual_values_fail_closed(name, value):
    with pytest.raises(ValueError):
        normalize_visual_value(name, value)


def test_stylesheet_cascade_and_inheritance_for_visual_values():
    from psx.css.parser import parse_stylesheet
    from psx.css.cascade import StyleTarget, resolve_style

    sheet = parse_stylesheet("div { background-color: #f80; font-family: Inter; font-size: 20px; color: #fff }")
    parent = resolve_style(sheet, StyleTarget("div"))
    assert parent.properties["background-color"] == CssColor("#f80")
    assert parent.properties["font-size"] == Length.px(20)
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    assert child.properties["font-family"] == "Inter"
    assert child.properties["color"] == CssColor("#fff")
    assert child.properties["background-color"] == CssColor("#0000")
