"""Transparent fragment regression tests for host child reconciliation."""

from psx.core.reconcile import _flatten_host_fragments
from psx.core.vnode import Fragment, NodeKind, create_element


def test_empty_fragment_does_not_create_native_child():
    empty = create_element(Fragment)
    assert _flatten_host_fragments((empty,)) == ()


def test_nested_fragment_preserves_native_sibling_order():
    first = create_element("span", "First")
    second = create_element("span", "Second")
    third = create_element("span", "Third")
    nested = create_element(Fragment, create_element(Fragment, second))
    result = _flatten_host_fragments((first, nested, third))
    assert result == (first, second, third)
    assert all(node.kind is not NodeKind.FRAGMENT for node in result)


def test_conditional_fragment_transition_preserves_other_siblings():
    fixed = create_element("span", "Fixed")
    message = create_element("div", "Success")
    empty = create_element(Fragment)
    visible = create_element(Fragment, message)
    assert _flatten_host_fragments((fixed, empty)) == (fixed,)
    assert _flatten_host_fragments((fixed, visible)) == (fixed, message)
    assert _flatten_host_fragments((fixed, empty)) == (fixed,)
