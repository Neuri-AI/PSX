"""Internal CSS property metadata and parser/cascade alignment regressions."""
import pytest

from psx.css.properties import CssValidationError, foundation_registry
from psx.css.parser import parse_stylesheet
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.visual_values import CssColor
from psx.css.effects import StyleEffect, classify_style_change
from psx.sfle.lengths import Length


def test_catalog_includes_geometry_paint_and_font_with_metadata():
    properties = foundation_registry().properties
    assert properties["width"].effect == "geometry"
    assert properties["background-color"].effect == "paint"
    assert properties["font-size"].effect == "measurement"
    assert properties["font-family"].inherited is True
    assert properties["margin-left"].allows_negative is True
    assert properties["padding"].allows_negative is False


def test_paint_declarations_are_validated_by_single_registry():
    registry = foundation_registry()
    assert registry.validate("background-color", "#fff").value == CssColor("#fff")
    assert registry.validate("font-size", "22px").value == Length.px(22)
    assert registry.validate("font-weight", "bold").value == 700
    with pytest.raises(CssValidationError) as exc:
        registry.validate("background-color", "url(unsafe)")
    assert exc.value.diagnostic.code == "invalid-value"


def test_cascade_respects_inheritance_and_background_is_not_inherited():
    parent = resolve_style(parse_stylesheet(
        "div { font-family: Inter; color: #aabbcc; background-color: #123 }"
    ), StyleTarget("div"))
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    assert child.properties["font-family"] == "Inter"
    assert child.properties["color"] == CssColor("#aabbcc")
    assert child.properties["background-color"] == CssColor("#0000")


def test_paint_change_does_not_require_geometry_but_font_change_does():
    old = resolve_style(parse_stylesheet("div {color: #000}"), StyleTarget("div"))
    paint = resolve_style(parse_stylesheet("div {color: #fff}"), StyleTarget("div"))
    measure = resolve_style(parse_stylesheet("div {font-size: 24px}"), StyleTarget("div"))
    assert classify_style_change(old, paint) == StyleEffect.PAINT
    assert classify_style_change(old, measure) & StyleEffect.MEASUREMENT
    assert classify_style_change(old, measure) & StyleEffect.GEOMETRY


def test_css_geometry_is_only_specified_not_applied_to_legacy_widgets():
    style = resolve_style(parse_stylesheet("button {width: 100px}"), StyleTarget("button"))
    assert style.properties["width"] == Length.px(100)
