"""Contract tests for the internal CSS property foundation."""

import pytest

from psx.css import CssProperty, CssPropertyRegistry, CssValidationError, foundation_registry
from psx.sfle.lengths import Length, LengthKind


def test_percentages_remain_symbolic():
    result = foundation_registry().validate("width", "50%")
    assert result.value == Length.percent(0.5)
    assert result.value.kind == LengthKind.PERCENT


def test_unknown_properties_fail_closed():
    with pytest.raises(CssValidationError) as error:
        foundation_registry().validate("some-future-prop", "12px")
    assert error.value.diagnostic.code == "unknown-property"


@pytest.mark.parametrize("value,code", [
    ("calc(100% - 2px)", "invalid-value"),
    ("12vw", "invalid-value"),
    ("-1px", "negative-value"),
    ("none", "unsupported-keyword"),
    (True, "invalid-value"),
])
def test_invalid_values_are_rejected(value, code):
    with pytest.raises(CssValidationError) as error:
        foundation_registry().validate("width", value)
    assert error.value.diagnostic.code == code


def test_registry_is_immutable_and_rejects_duplicate_definitions():
    registry = foundation_registry()
    with pytest.raises(TypeError):
        registry.properties["width"] = registry.properties["height"]
    with pytest.raises(ValueError, match="Duplicate"):
        CssPropertyRegistry((CssProperty("width", Length.px(0), False), CssProperty("width", Length.px(0), False)))


def test_existing_native_width_semantics_are_not_modified():
    # Pure validation: the CSS registry deliberately does not import VNodes or adapters.
    assert foundation_registry().validate("width", "150px").value == Length.px(150)


def test_border_color_is_a_noninherited_typed_paint_property():
    from psx.css.visual_values import CssColor
    registry = foundation_registry()
    prop = registry.properties["border-color"]
    assert prop.inherited is False
    assert prop.effect == "paint"
    assert registry.validate("border-color", "#aBc").value == CssColor("#abc")


@pytest.mark.parametrize("invalid", ["rgba(1, 2, 3, 1)", "#12345", "url(x)"])
def test_border_color_rejects_unsupported_color_notation(invalid):
    with pytest.raises(CssValidationError) as error:
        foundation_registry().validate("border-color", invalid)
    assert error.value.diagnostic.code == "invalid-value"
