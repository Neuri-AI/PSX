"""Shared CSS input box-model parity: no native toolkit required."""

import pytest

from psx.css.markup import compute_markup_styles
from psx.css.native_paint import native_control_padding
from psx.css.parser import parse_stylesheet
from psx import psx


@pytest.mark.parametrize("tag", ["input", "textarea"])
@pytest.mark.parametrize("declaration, expected", [
    ("padding: 8px", (8.0, 8.0, 8.0, 8.0)),
    ("padding: 6px 12px", (12.0, 6.0, 12.0, 6.0)),
    ("padding: 1px 2px 3px 4px", (4.0, 1.0, 2.0, 3.0)),
    ("padding-left: 13px; padding-top: 5px", (13.0, 5.0, 0.0, 0.0)),
])
def test_input_padding_css_uses_shared_side_order(tag, declaration, expected):
    node = psx(f'<{tag} class="field" />')
    styled = compute_markup_styles(
        node, parse_stylesheet(f".field {{ {declaration}; }}")
    )
    assert native_control_padding(styled.css_computed) == expected


def test_input_without_authored_padding_preserves_native_default():
    node = psx('<input type="text" />')
    assert native_control_padding(node.css_computed) is None


def test_input_padding_updates_from_css_instead_of_sticky_native_state():
    node = psx('<input class="field" />')
    one = compute_markup_styles(node, ".field { padding: 4px; }")
    two = compute_markup_styles(node, ".field { padding: 12px 8px; }")
    assert native_control_padding(one.css_computed) == (4.0, 4.0, 4.0, 4.0)
    assert native_control_padding(two.css_computed) == (8.0, 12.0, 8.0, 12.0)
