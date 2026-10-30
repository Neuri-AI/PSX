from psx.css.properties import foundation_registry
from psx.sfle.lengths import LengthKind

def test_margin_auto_is_valid():
    assert foundation_registry().validate('margin-left', 'auto').value.kind is LengthKind.AUTO

from psx.css.parser import parse_stylesheet
from psx.css.cascade import resolve_style, StyleTarget


def test_margin_shorthand_autocenter():
    style = resolve_style(
        parse_stylesheet("div { margin: 0 auto }"), StyleTarget("div")
    )
    assert style.properties["margin-left"].kind is LengthKind.AUTO
    assert style.properties["margin-right"].kind is LengthKind.AUTO


def test_cursor_keywords():
    keywords = (
        "auto", "default", "none", "context-menu", "help",
        "pointer", "progress", "wait",
    )
    for keyword in keywords:
        result = resolve_style(
            parse_stylesheet("a { cursor: " + keyword + " }"),
            StyleTarget("a"),
        )
        assert result.properties["cursor"] == keyword
