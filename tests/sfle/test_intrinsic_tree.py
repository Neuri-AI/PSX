"""Measured leaf flex input integration tests."""
import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.flex_math import FlexBasis
from psx.sfle.intrinsic_tree import IntrinsicLeafStyle, compute_measured_leaf_tree
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.line_layout import FlexDirection
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox,
)

METRIC = IntrinsicSizes(20, 60, 8, 25, 60, 22)
CONSTRAINTS = LayoutConstraints(AvailableSize(150, True), AvailableSize(80, True))
MEASURE = MeasuredBox("leaf", METRIC, CONSTRAINTS, 2)


def test_leaf_auto_basis_uses_intrinsic_max_content_not_final_used_width():
    tree = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0, grow=1, shrink=1), 0)),
    )
    result = compute_measured_leaf_tree(
        tree, measurements=(MEASURE,),
        leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
        generation=1,
    )
    boxes = {box.node_id: box for box in result.boxes}
    assert boxes["leaf"].content.width == 150
    assert boxes["leaf"].content.height == 22


def test_column_leaf_intrinsic_main_axis_uses_measured_height():
    tree = (
        MarginTreeNode("root", None, 80, 100, direction=FlexDirection.COLUMN),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0, grow=0, shrink=0), 0)),
    )
    result = compute_measured_leaf_tree(
        tree, measurements=(MEASURE,),
        leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
        generation=1,
    )
    leaf = result.boxes[1]
    assert leaf.content.height == 25
    assert leaf.content.width == 60


def test_missing_leaf_metrics_fail_closed():
    tree = (
        MarginTreeNode("root", None, 100, 100),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0), 0)),
    )
    with pytest.raises(SFLEError, match="Missing accepted"):
        compute_measured_leaf_tree(
            tree, measurements=(),
            leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
            generation=1,
        )


def test_non_leaf_intrinsic_declaration_is_rejected():
    tree = (
        MarginTreeNode("root", None, 100, 100),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0), 0)),
    )
    with pytest.raises(SFLEError, match="childless"):
        compute_measured_leaf_tree(
            tree, measurements=(MEASURE,),
            leaves=(IntrinsicLeafStyle("root", Length(LengthKind.AUTO)),),
            generation=1,
        )
