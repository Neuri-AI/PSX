"""Explicit CSS background paint conversion is native-backend independent."""
import pytest

from psx.css.native_paint import background_hex, background_rgba, foreground_hex, foreground_rgba
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet


def _style(css):
    return resolve_style(parse_stylesheet(css), StyleTarget("div"))


def test_background_only_applies_when_authored():
    assert background_rgba(_style("")) is None
    assert background_hex(_style("div {background-color: #123456}")) == "#123456"


def test_rgba_expansion_preserves_alpha_without_silent_loss():
    style = _style("div {background-color: #f008}")
    assert background_rgba(style) == (1.0, 0.0, 0.0, 136 / 255)
    with pytest.raises(ValueError, match="opaque"):
        background_hex(style)


def test_css_background_can_be_removed_without_inheriting_parent_background():
    parent = _style("div {background-color: #00ff00}")
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    assert background_hex(parent) == "#00ff00"
    assert background_hex(child) is None


def test_explicit_foreground_is_distinct_from_registry_default():
    assert foreground_hex(_style("")) is None
    assert foreground_hex(_style("div {color: #aBc}")) == "#aabbcc"


def test_authored_foreground_inherits_without_inheriting_background():
    parent = _style("div {color: #123456; background-color: #abcdef}")
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    grandchild = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=child)
    assert foreground_hex(child) == "#123456"
    assert foreground_hex(grandchild) == "#123456"
    assert background_hex(child) is None
    overridden = resolve_style(parse_stylesheet("span {color: #aabbcc}"), StyleTarget("span"), inherited=parent)
    assert foreground_hex(overridden) == "#aabbcc"


def test_implicit_foreground_never_becomes_explicit_through_inheritance():
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=_style(""))
    assert foreground_hex(child) is None


def test_translucent_foreground_preserves_alpha_and_fails_closed_for_hex():
    style = _style("div {color: #f008}")
    assert foreground_rgba(style) == (1.0, 0.0, 0.0, 136 / 255)
    with pytest.raises(ValueError, match="opaque"):
        foreground_hex(style)
