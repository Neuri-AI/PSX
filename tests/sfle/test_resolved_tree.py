"""Restricted nested Flex geometry must preserve parent offsets and sizing."""
import pytest
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection
from psx.sfle.resolved_tree import ResolvedTreeNode, compute_resolved_tree
from psx.sfle.model import WritingDirection
from psx.sfle.errors import SFLEError

def flex(n, grow=0):
    return FlexBasis(basis=n, hypothetical=n, min_size=0, max_size=None, grow=grow, shrink=1)

def node(id, parent, width, height, basis=None, grow=0):
    return ResolvedTreeNode(id, parent, width, height, None if basis is None else flex(basis, grow))

def test_nested_offset_includes_parent_position():
    root = ResolvedTreeNode("root", None, 200, 80, main_gap=10)
    a = node("a", "root", 40, 20, 40)
    b = node("b", "root", 100, 40, 100)
    c = node("c", "b", 30, 10, 30)
    boxes = dict(compute_resolved_tree((root, a, b, c), generation=8).boxes)
    assert boxes["b"].content.x == 50
    assert boxes["c"].content.x == 50
    assert boxes["c"].content.y == 0
    assert boxes["c"].border == boxes["c"].content

def test_nested_row_rtl_respects_physical_coordinates():
    root = ResolvedTreeNode("root", None, 200, 80)
    parent = node("parent", "root", 100, 40, 100)
    child = node("child", "parent", 25, 10, 25)
    boxes = dict(compute_resolved_tree((root, parent, child), generation=8,
                                      writing=WritingDirection.RTL).boxes)
    assert boxes["parent"].content.x == 100
    assert boxes["child"].content.x == 175

def test_parent_flex_grow_changes_nested_origin():
    root = node("root", None, 200, 80)
    a = node("a", "root", 20, 20, 20, grow=1)
    parent = node("parent", "root", 20, 40, 20, grow=1)
    child = node("child", "parent", 10, 10, 10)
    boxes = dict(compute_resolved_tree((root,a,parent,child), generation=8).boxes)
    assert boxes["a"].content.width == 100
    assert boxes["parent"].content.x == 100
    assert boxes["parent"].content.width == 100
    assert boxes["child"].content.x == 100

def test_rejects_nonpreorder_and_missing_flex_basis():
    with pytest.raises(SFLEError):
        compute_resolved_tree((node("root",None,100,20),node("a","missing",10,10,10)),generation=8)
    with pytest.raises(SFLEError):
        compute_resolved_tree((node("root",None,100,20),node("a","root",10,10)),generation=8)
