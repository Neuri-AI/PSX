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
    "div {color:red}",
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
