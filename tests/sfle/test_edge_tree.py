"""Nested padding and border boxes must compose through content origins."""
import pytest
from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
from psx.sfle.edge_tree import EdgeTreeNode, compute_edge_tree
from psx.sfle.errors import SFLEError
from psx.sfle.flex_math import FlexBasis

def basis(n, grow=0):
    return FlexBasis(n,n,grow=grow,shrink=1,min_size=0)

def test_nested_content_origin_uses_root_and_parent_edges():
    root_edges = UsedBoxEdges(padding=UsedEdges(top=3,left=5),border=UsedEdges(top=2,left=1))
    child_edges = UsedBoxEdges(padding=UsedEdges(top=4,left=6),border=UsedEdges(top=1,left=2))
    nodes = (
        EdgeTreeNode("root",None,200,80,edges=root_edges),
        EdgeTreeNode("parent","root",50,30,flex=basis(50),edges=child_edges),
        EdgeTreeNode("leaf","parent",10,10,flex=basis(10)),
    )
    boxes = dict(compute_edge_tree(nodes,generation=8).boxes)
    assert (boxes["root"].content.x,boxes["root"].content.y)==(6,5)
    assert (boxes["parent"].border.x,boxes["parent"].border.y)==(6,5)
    assert (boxes["parent"].content.x,boxes["parent"].content.y)==(14,10)
    assert (boxes["leaf"].border.x,boxes["leaf"].border.y)==(14,10)
    assert boxes["parent"].content.width==50
    assert boxes["leaf"].content.width==10

def test_parent_flex_distribution_reflows_nested_child():
    nodes = (
        EdgeTreeNode("root",None,200,80),
        EdgeTreeNode("a","root",20,20,flex=basis(20,1)),
        EdgeTreeNode("b","root",20,30,flex=basis(20,1),
                     edges=UsedBoxEdges(padding=UsedEdges(left=5,right=5))),
        EdgeTreeNode("leaf","b",10,10,flex=basis(10)),
    )
    boxes = dict(compute_edge_tree(nodes,generation=8).boxes)
    assert boxes["a"].content.width == pytest.approx(95)
    assert boxes["b"].border.x == pytest.approx(95)
    assert boxes["b"].content.x == pytest.approx(100)
    assert boxes["leaf"].border.x == pytest.approx(100)

def test_nonzero_outer_margin_is_explicitly_unsupported():
    with pytest.raises(SFLEError):
        compute_edge_tree((EdgeTreeNode("root",None,200,80),
            EdgeTreeNode("a","root",10,10,flex=basis(10),
                edges=UsedBoxEdges(margin=UsedEdges(left=5)))),generation=8)
