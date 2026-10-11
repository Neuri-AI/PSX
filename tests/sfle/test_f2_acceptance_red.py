"""F2 acceptance RED phase, pinned to baseline 2ad3df17.

These tests intentionally fail until their named end-to-end behaviors work.
Do not relax them to match the existing restricted helper implementations.
"""
import pytest

from psx.sfle.auto_cross_tree import AutoCrossSize, compute_auto_cross_tree
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection


def _item(name: str, main: float, cross: float, grow: float = 0):
    return MarginFlexItem(
        name, FlexBasis(main, main, grow=grow, shrink=1, min_size=0),
        cross,
    )


def test_A01_orthogonal_auto_parent_height_from_descendant():
    """A01: row -> column -> multiline text, final auto parent height 60px.

    The text metric is 3 lines x 20px and width is the final 80px allocation.
    A production test will additionally drive constrained UI measurement and
    compare the browser. This test first exposes the orthogonal-auto blocker.
    """
    nodes = (
        MarginTreeNode("root", None, 120, 0, direction=FlexDirection.ROW),
        MarginTreeNode(
            "fixed", "root", 40, 10, _item("fixed", 40, 10),
        ),
        MarginTreeNode(
            "column", "root", 80, 0, _item("column", 80, 0),
            direction=FlexDirection.COLUMN,
        ),
        MarginTreeNode("text", "column", 80, 60, _item("text", 60, 80)),
    )
    result = compute_auto_cross_tree(
        nodes,
        auto_cross=(AutoCrossSize("column"), AutoCrossSize("root")),
        generation=1,
    )
    by_id = {box.node_id: box for box in result.boxes}
    assert by_id["column"].content.height == pytest.approx(60, abs=0.01)
    assert by_id["root"].content.height == pytest.approx(60, abs=0.01)


def test_A08_python_compute_is_a_real_fallback_not_a_placeholder():
    """A08: fallback must compute a supported definite, empty Flex tree."""
    snapshot = LayoutInput(
        1, 1, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True)),
        (LayoutNode("root", None, "Flex", ()),), (),
    )
    result = PythonLayoutEngine().compute(snapshot)
    assert result.generation == 1
    assert len(result.boxes) == 1
