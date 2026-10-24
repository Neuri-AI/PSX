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
    "div span article {width:5px}",
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


def test_direct_child_selector_matches_only_immediate_parent():
    stylesheet = parse_stylesheet(
        ".color-list { display: flex; flex-direction: row; width: 100% }"
        ".color-list > div { flex: 1 }"
    )
    parent = StyleTarget("div", frozenset({"color-list"}))
    immediate = resolve_style(stylesheet, StyleTarget("div", parent=parent))
    nested = resolve_style(stylesheet, StyleTarget(
        "div", parent=StyleTarget("section", parent=parent)))
    unrelated = resolve_style(stylesheet, StyleTarget("div"))
    assert immediate.properties["flex-grow"] == 1.0
    assert immediate.properties["flex-shrink"] == 1.0
    assert immediate.properties["flex-basis"] == Length.percent(0)
    assert "flex-grow" in immediate.specified
    assert "flex-grow" not in nested.specified
    assert "flex-grow" not in unrelated.specified
    assert parse_selector(".color-list > div").specificity == (0, 1, 1)


@pytest.mark.parametrize("selector", (".a > ", " > div", ".a > div > span", ".a div span"))
def test_unsupported_or_malformed_relationships_still_fail_closed(selector):
    with pytest.raises(CssSyntaxError):
        parse_selector(selector)


@pytest.mark.parametrize("value", ("-1", "not-a-number", "1 1 auto", "NaN"))
def test_unsupported_flex_shorthand_values_fail_closed(value):
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(f".color-list > div {{ flex: {value}; }}")


@pytest.mark.parametrize("value,expected", (
    ("20px", (20, 20, 20, 20)),
    ("20px 12px", (20, 12, 20, 12)),
    ("20px 12px 8px", (20, 12, 8, 12)),
    ("20px 12px 8px 4px", (20, 12, 8, 4)),
))
@pytest.mark.parametrize("name", ("padding", "margin"))
def test_clockwise_box_shorthand_resolves_all_sides(name, value, expected):
    resolved = resolve_style(parse_stylesheet(f"div {{{name}: {value}}}"), StyleTarget("div"))
    assert tuple(resolved.properties[f"{name}-{side}"] for side in
                 ("top", "right", "bottom", "left")) == tuple(Length.px(x) for x in expected)


def test_clockwise_shorthand_respects_order_and_inline_mapping():
    from psx.css.markup import parse_markup_style
    resolved = resolve_style(parse_stylesheet(
        "div { padding-left: 7px; padding: 20px 12px; padding-top: 3px }"
    ), StyleTarget("div"))
    assert resolved.properties["padding-left"] == Length.px(12)
    assert resolved.properties["padding-top"] == Length.px(3)
    source = parse_markup_style("div", inline_value={
        "padding": "20px 12px", "padding-right": "5px",
    })
    inline = resolve_style(parse_stylesheet(""), StyleTarget("div"), inline=source.inline)
    assert inline.properties["padding-left"] == Length.px(12)
    assert inline.properties["padding-right"] == Length.px(5)


@pytest.mark.parametrize("name,value", (
    ("padding", "20px 12px 8px 4px 1px"),
    ("padding", "20px -1px"),
    ("padding", "auto 12px"),
    ("padding", "20px garbage"),
    ("margin", "2px invalid"),
))
def test_invalid_clockwise_box_values_fail_closed(name, value):
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(f"div {{{name}: {value}}}")


def test_descendant_selector_matches_non_immediate_ancestor():
    sheet = parse_stylesheet(".sidebar-content button { text-align: left }")
    parent = StyleTarget("div", frozenset({"sidebar-content"}))
    nested = StyleTarget("section", parent=parent)
    match = resolve_style(sheet, StyleTarget("button", parent=nested))
    miss = resolve_style(sheet, StyleTarget("button"))
    assert match.properties["text-align"] == "left"
    assert "text-align" in match.specified
    assert "text-align" not in miss.specified


def test_solid_border_shorthand_expands_into_typed_native_values():
    sheet = parse_stylesheet("button {border: 2px solid #ff0000; border-radius: 6px}")
    computed = resolve_style(sheet, StyleTarget("button"))
    assert computed.properties["border-width"] == Length.px(2)
    assert computed.properties["border-color"].value == "#ff0000"
    assert computed.properties["border-radius"] == Length.px(6)


@pytest.mark.parametrize("bad", (
    "2px dotted red", "solid", "2px solid", "invalid solid red",
))
def test_unsupported_border_shorthand_fails_closed(bad):
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(f"button {{border: {bad}}}")


def test_border_none_and_pointer_cursor_in_button_styles():
    sheet = parse_stylesheet(
        "button {border: 2px solid #123456; border: none; "
        "cursor: pointer; padding: 0px 10px}"
    )
    computed = resolve_style(sheet, StyleTarget("button"))
    assert computed.properties["border-width"] == Length.px(0)
    assert computed.properties["cursor"] == "pointer"
    assert computed.properties["padding-left"] == Length.px(10)
    assert computed.properties["padding-right"] == Length.px(10)
    assert computed.properties["padding-top"] == Length.px(0)


@pytest.mark.parametrize("invalid", ("grab", "wait", "pointer extra"))
def test_cursor_rejects_unsupported_values(invalid):
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(f"button {{cursor: {invalid}}}")


@pytest.mark.parametrize("side", ("top", "right", "bottom", "left"))
def test_side_border_shorthand_validates_width_and_color(side):
    sheet = parse_stylesheet(f"div {{border-{side}: 1px solid #e0e0e0}}")
    computed = resolve_style(sheet, StyleTarget("div"))
    assert computed.properties[f"border-{side}-width"] == Length.px(1)
    assert computed.properties[f"border-{side}-color"].value == "#e0e0e0"
    assert computed.properties["border-width"] == Length.px(0)


def test_side_border_none_resets_only_selected_edge():
    computed = resolve_style(parse_stylesheet(
        "div { border: 2px solid #123456; border-bottom: none }"
    ), StyleTarget("div"))
    assert computed.properties["border-width"] == Length.px(2)
    assert computed.properties["border-bottom-width"] == Length.px(0)


def test_invalid_side_border_rejected():
    with pytest.raises(CssSyntaxError):
        parse_stylesheet("div {border-bottom: 1px dashed #e0e0e0}")
