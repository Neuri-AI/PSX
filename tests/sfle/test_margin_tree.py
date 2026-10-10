"""Nested resolved margin/alignment fixtures: parent content origin and RTL."""
from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
from psx.sfle.flex_math import FlexBasis
from psx.sfle.main_alignment import JustifyContent
from psx.sfle.cross_alignment import CrossAlign
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode, compute_margin_tree
from psx.sfle.model import WritingDirection


def item(name: str, basis: float, *, padding: float = 0) -> MarginFlexItem:
    return MarginFlexItem(
        name, FlexBasis(basis, basis, grow=0, shrink=0, min_size=0),
        20, edges=UsedBoxEdges(padding=UsedEdges(left=padding)),
    )


def test_nested_justify_uses_parent_content_box_after_padding():
    root = MarginTreeNode("root", None, 200, 80,
        edges=UsedBoxEdges(padding=UsedEdges(left=5)),
        justify=JustifyContent.CENTER)
    parent = MarginTreeNode("parent", "root", 100, 40, item("parent", 100, padding=6),
        justify=JustifyContent.FLEX_END)
    leaf = MarginTreeNode("leaf", "parent", 20, 20, item("leaf", 20))
    boxes = {b.node_id: b for b in compute_margin_tree((root, parent, leaf), generation=8).boxes}
    # Outer parent border is 106 wide; center in root 200-wide content.
    assert boxes["parent"].border.x == 52
    # Parent content begins at +6, and flex-end aligns the 20-wide leaf at +80.
    assert boxes["leaf"].border.x == 138


def test_nested_rtl_start_and_cross_alignment():
    root = MarginTreeNode("root", None, 200, 80,
        align_items=CrossAlign.CENTER)
    parent = MarginTreeNode("parent", "root", 100, 40, item("parent", 100))
    leaf = MarginTreeNode("leaf", "parent", 20, 20, item("leaf", 20))
    result = compute_margin_tree((root, parent, leaf), generation=8,
                                  writing=WritingDirection.RTL)
    boxes = {b.node_id: b for b in result.boxes}
    assert boxes["parent"].border.x == 100
    assert boxes["leaf"].border.x == 180


def test_empty_nodes_and_root_padding_are_preserved():
    assert compute_margin_tree((), generation=8).boxes == ()
    root = MarginTreeNode("root", None, 40, 20,
        edges=UsedBoxEdges(padding=UsedEdges(left=4, top=3)))
    box, = compute_margin_tree((root,), generation=8).boxes
    assert (box.content.x, box.content.y) == (4, 3)


def test_nested_auto_and_signed_main_margins_remain_distinct_from_box_size():
    from psx.sfle.main_margins import UsedMargin
    root = MarginTreeNode("root", None, 200, 80)
    leading = MarginFlexItem(
        "leading", FlexBasis(20, 20, grow=0, shrink=0, min_size=0), 20,
        main_start=UsedMargin(-5),
    )
    parent_item = MarginFlexItem(
        "parent", FlexBasis(50, 50, grow=0, shrink=0, min_size=0), 40,
        main_start=UsedMargin(None),
    )
    leaf = item("leaf", 10)
    nodes = (
        root,
        MarginTreeNode("leading", "root", 20, 20, leading),
        MarginTreeNode("parent", "root", 50, 40, parent_item),
        MarginTreeNode("leaf", "parent", 10, 20, leaf),
    )
    boxes = {box.node_id: box for box in compute_margin_tree(nodes, generation=8).boxes}
    assert boxes["leading"].border.x == -5
    assert boxes["parent"].border.x == 150
    assert boxes["parent"].used_main_start_margin == 135
    assert boxes["leaf"].border.x == 150
