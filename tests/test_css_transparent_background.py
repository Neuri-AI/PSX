"""Transparent CSS backgrounds survive parsing and native paint projection."""

import pytest

from psx.css.parser import parse_stylesheet
from psx.css.visual_values import CssColor
from psx.css.native_paint import background_hex, background_rgba, qt_semantic_stylesheet


@pytest.mark.parametrize("property_name", ["background", "background-color"])
def test_transparent_shorthand_and_longhand(property_name):
    stylesheet = parse_stylesheet(f"button {{ {property_name}: transparent; }}")
    assert stylesheet.rules[0].declarations == (
        ("background-color", CssColor("#00000000")),
    )


def test_transparent_color_normalized_case_insensitive():
    stylesheet = parse_stylesheet("div { background: TRANSPARENT; }")
    assert stylesheet.rules[0].declarations[0][1] == CssColor("#00000000")
