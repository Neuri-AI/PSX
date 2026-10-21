"""HTML-like aliases retain the existing portable native component contracts."""
from __future__ import annotations

import pytest

from psx import psx


@pytest.mark.parametrize("markup,expected", (
    ('<checkbox checked={checked} />', "Checkbox"),
    ('<radio value="primary" label="Primary" />', "Radio"),
    ('<radiogroup value="primary"><radio value="primary" label="Primary"/></radiogroup>', "RadioGroup"),
    ('<select options={options} value="primary" />', "Select"),
    ('<a href="https://example.org">Visit</a>', "Link"),
    ('<badge>Ready</badge>', "Badge"),
))
def test_lowercase_control_alias_uses_native_component_contract(markup, expected):
    node = psx(markup, scope={
        "checked": True,
        "options": ({"label": "Primary", "value": "primary"},),
    })
    assert node.type == expected
    if expected == "RadioGroup":
        assert node.children[0].type == "Radio"
    if expected == "Link":
        assert node.props["label"] == "Visit"
        assert node.props["href"] == "https://example.org"
    if expected == "Badge":
        assert node.props["label"] == "Ready"


def test_lowercase_aliases_preserve_css_computed_source():
    node = psx('<select options={options} style="color: #123456; border-radius: 8px"/>',
               scope={"options": ({"label": "Alpha", "value": "a"},)})
    assert node.type == "Select"
    assert node.css_computed.properties["color"].value == "#123456"


@pytest.mark.parametrize("markup", (
    '<checkbox>not allowed</checkbox>',
    '<select>unregistered option content</select>',
    '<radio value="a">not allowed</radio>',
))
def test_lowercase_control_alias_preserves_closed_child_policy(markup):
    from psx.core.errors import MarkupSyntaxError
    with pytest.raises((MarkupSyntaxError, TypeError, ValueError)):
        psx(markup)
