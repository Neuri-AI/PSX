"""PSX-to-CSS projection has no renderer effects or public prop mutation."""
import pytest

from psx.core.vnode import create_element
from psx.css.cascade import StyleTarget
from psx.css.parser import parse_stylesheet
from psx.css.properties import foundation_registry
from psx.css.tree import resolve_vnode_styles
from psx.css.visual_values import CssColor
from psx.sfle.lengths import Length


def test_project_vnode_tree_without_mutation():
    child = create_element("span", "Hello", key="stable")
    root = create_element("div", child, key="root")
    old_props = dict(root.props)
    sheet = parse_stylesheet(".panel {color: #fff; width: 50%} span {font-size: 20px}")
    nodes = resolve_vnode_styles(
        root, sheet, selectors={(): StyleTarget("div", frozenset({"panel"}))}
    )
    assert nodes[0].computed.properties["width"] == Length.percent(0.5)
    assert nodes[1].computed.properties["color"] == CssColor("#fff")
    assert nodes[1].computed.properties["font-size"] == Length.px(20)
    assert nodes[1].key == "stable"
    assert root.props == old_props
    assert root.children[0] is child


def test_explicit_inline_style_overrides_stylesheet_without_native_commit():
    root = create_element("div")
    declarations = (foundation_registry().validate("width", "75px"),)
    nodes = resolve_vnode_styles(
        root, parse_stylesheet("div {width: 20px}"), inline={(): declarations}
    )
    assert nodes[0].computed.properties["width"] == Length.px(75)


def test_mismatched_tag_is_rejected():
    root = create_element("div")
    with pytest.raises(ValueError, match="does not match"):
        resolve_vnode_styles(root, parse_stylesheet(""), selectors={(): StyleTarget("span")})


def test_keyed_reorder_changes_paths_but_not_identity_or_state():
    a = create_element("span", "A", key="a")
    b = create_element("span", "B", key="b")
    original = create_element("div", a, b)
    reordered = create_element("div", b, a)
    sheet = parse_stylesheet("span { color: #abc }")
    assert [item.key for item in resolve_vnode_styles(original, sheet) if item.tag == "span"] == ["a", "b"]
    assert [item.key for item in resolve_vnode_styles(reordered, sheet) if item.tag == "span"] == ["b", "a"]
    assert original.children[0] is a
    assert reordered.children[1] is a
