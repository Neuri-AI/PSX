import pytest

from psx.css.parser import CssSyntaxError, parse_selector, parse_stylesheet
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.properties import foundation_registry
from psx.sfle.lengths import Length


def test_selector_specificity_and_matching():
    selector = parse_selector("div.card#hero")
    assert selector.specificity == (1, 1, 1)
    assert selector.matches("div", frozenset({"card", "selected"}), "hero")
    assert not selector.matches("span", frozenset({"card"}), "hero")


def test_cascade_specificity_and_source_order():
    stylesheet = parse_stylesheet("div {width: 10px} .card {width:20px} #hero {width:30px} div {height:50%}")
    computed = resolve_style(stylesheet, StyleTarget("div", frozenset({"card"}), "hero"))
    assert computed.properties["width"] == Length.px(30)
    assert computed.properties["height"] == Length.percent(0.5)


def test_inline_wins_and_does_not_mutate_sheet():
    sheet = parse_stylesheet("div {width: 10px}")
    declaration = foundation_registry().validate("width", "45px")
    resolved = resolve_style(sheet, StyleTarget("div"), inline=(declaration,))
    assert resolved.properties["width"] == Length.px(45)
    assert resolve_style(sheet, StyleTarget("div")).properties["width"] == Length.px(10)


@pytest.mark.parametrize("source", [
    "@media screen {div {width:2px}}",
    "div span {width:5px}",
    "div {width: calc(1px + 1px)}",
    "div { width:10px",
    "div {color:rgb(1,2,3)}",
    "div {width:1px!important}",
])
def test_unsupported_syntax_fails_closed(source):
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(source)


def test_computed_style_is_read_only():
    result = resolve_style(parse_stylesheet(""), StyleTarget("div"))
    with pytest.raises(TypeError):
        result.properties["width"] = Length.px(99)


def test_stylesheet_source_is_bounded():
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(" " * 262145)


def test_background_solid_color_shorthand_matches_longhand():
    from psx.css.markup import parse_markup_style

    source = parse_markup_style("div", inline_value="background: #ff0000; color: #ffffff")
    assert [declaration.name for declaration in source.inline] == ["background-color", "color"]
    computed = resolve_style(parse_stylesheet("div { background: red }"), StyleTarget("div"))
    assert str(computed.properties["background-color"]) == str(
        foundation_registry().validate("background-color", "red").value
    )


def test_background_image_shorthand_is_not_silently_accepted():
    with pytest.raises(CssSyntaxError):
        parse_stylesheet("div { background: url(image.png) }")


def test_flex_css_longhands_validate_typed_values():
    registry = foundation_registry()
    sheet = parse_stylesheet(
        "div { display: flex; flex-direction: row; gap: 10px;"
        " flex-wrap: wrap; justify-content: space-between;"
        " align-items: center; align-content: stretch;"
        " flex-grow: 2.5; flex-shrink: 0; flex-basis: 30px;"
        " align-self: flex-end; order: -2; }"
    )
    computed = resolve_style(sheet, StyleTarget("div"))
    assert computed.properties["display"] == "flex"
    assert computed.properties["flex-direction"] == "row"
    assert computed.properties["gap"] == Length.px(10)
    assert computed.properties["flex-grow"] == 2.5
    assert computed.properties["flex-shrink"] == 0
    assert computed.properties["flex-basis"] == Length.px(30)
    assert computed.properties["order"] == -2


@pytest.mark.parametrize("name,value", (
    ("display", "table"), ("flex-direction", "sideways"),
    ("flex-grow", "-1"), ("flex-grow", "NaN"),
    ("order", "1.5"), ("flex-basis", "-2px"),
))
def test_invalid_flex_css_is_rejected(name, value):
    from psx.css.properties import CssValidationError
    with pytest.raises(CssValidationError):
        foundation_registry().validate(name, value)
