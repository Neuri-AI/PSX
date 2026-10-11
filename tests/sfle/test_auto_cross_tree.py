"""Bounded auto cross-axis container sizing contract."""
import pytest

from psx.sfle.auto_cross_tree import AutoCrossSize, compute_auto_cross_tree
from psx.sfle.errors import SFLECapabilityError
from psx.sfle.flex_math import FlexBasis
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.line_layout import FlexWrap


def item(id, cross):
    return MarginFlexItem(id, FlexBasis(20, 20, grow=0, shrink=0), cross)


def test_nested_nowrap_auto_height_uses_child_cross_contribution():
    nodes = (
        MarginTreeNode("root", None, 100, 80),
        MarginTreeNode("parent", "root", 20, 0, item("parent", 0)),
        MarginTreeNode("a", "parent", 20, 15, item("a", 15)),
        MarginTreeNode("b", "parent", 20, 30, item("b", 30)),
    )
    result = compute_auto_cross_tree(nodes, auto_cross=(AutoCrossSize("parent"),), generation=2)
    boxes = {b.node_id: b for b in result.boxes}
    assert boxes["parent"].content.height == 30
    assert boxes["b"].content.height == 30


def test_two_level_auto_cross_sizes_resolve_bottom_up():
    nodes = (
        MarginTreeNode("root", None, 100, 80),
        MarginTreeNode("outer", "root", 20, 0, item("outer", 0)),
        MarginTreeNode("inner", "outer", 20, 0, item("inner", 0)),
        MarginTreeNode("leaf", "inner", 20, 17, item("leaf", 17)),
    )
    result = compute_auto_cross_tree(nodes, auto_cross=(
        AutoCrossSize("outer"), AutoCrossSize("inner"),
    ), generation=2)
    assert result.boxes[1].content.height == 17
    assert result.boxes[2].content.height == 17


def test_wrap_auto_cross_is_not_silently_approximated():
    nodes = (
        MarginTreeNode("root", None, 100, 80, wrap=FlexWrap.WRAP),
        MarginTreeNode("leaf", "root", 20, 10, item("leaf", 10)),
    )
    with pytest.raises(SFLECapabilityError):
        compute_auto_cross_tree(nodes, auto_cross=(AutoCrossSize("root"),), generation=2)
