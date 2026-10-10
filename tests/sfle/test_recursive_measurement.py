"""Resolved Flex geometry -> native measurement integration contracts."""
import pytest

from psx.sfle.constraint_propagation import ChildSizing
from psx.sfle.errors import SFLEError
from psx.sfle.headless_measurement import HeadlessMeasurementSource
from psx.sfle.lengths import Length
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.flex_math import FlexBasis
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    WritingDirection,
)
from psx.sfle.recursive_measurement import measure_resolved_margin_tree

CONSTRAINT = LayoutConstraints(AvailableSize(240, True), AvailableSize(90, True))
METRICS = IntrinsicSizes(10, 30, 5, 15, 20, 10)
ROOT = LayoutNode("root", None, "Flex", ())
CHILD = LayoutNode("child", "root", "Flex", ())
NODES = (
    MarginTreeNode("root", None, 240, 90),
    MarginTreeNode(
        "child", "root", 40, 20,
        MarginFlexItem("child", FlexBasis(40, 40, shrink=0, grow=0), 20),
    ),
)
SIZING = (("child", ChildSizing(Length.px(40), Length.px(20))),)
SOURCE = HeadlessMeasurementSource((("root", METRICS), ("child", METRICS)))


def snapshot(generation=5, measurements=()):
    return LayoutInput(1, generation, WritingDirection.LTR, CONSTRAINT, (ROOT, CHILD), measurements)


def test_recursive_measurement_preserves_used_parent_content_and_leaf_geometry():
    result = measure_resolved_margin_tree(
        snapshot(), NODES, child_sizing=SIZING,
        port=SOURCE.port(), current_generation=5,
    )
    assert tuple(x.node_id for x in result.measurements) == ("child", "root")
    assert result.deferred == ()
    assert result.geometry.boxes[1].content.width == 40
    assert result.measurements[0].constraints.width.value == 40


def test_recursive_measurement_reuses_current_snapshots():
    first = measure_resolved_margin_tree(
        snapshot(), NODES, child_sizing=SIZING,
        port=SOURCE.port(), current_generation=5,
    )
    second = measure_resolved_margin_tree(
        snapshot(measurements=first.measurements),
        NODES, child_sizing=SIZING, port=SOURCE.port(), current_generation=5,
    )
    assert second.measurements == first.measurements


def test_recursive_measurement_rejects_stale_generation_before_native_measure():
    with pytest.raises(SFLEError, match="Stale"):
        measure_resolved_margin_tree(
            snapshot(), NODES, child_sizing=SIZING,
            port=SOURCE.port(), current_generation=6,
        )


def test_recursive_measurement_rejects_mismatched_parents():
    wrong = (NODES[0], MarginTreeNode(
        "child", None, 40, 20,
        MarginFlexItem("child", FlexBasis(40, 40), 20),
    ))
    with pytest.raises(SFLEError, match="parent"):
        measure_resolved_margin_tree(
            snapshot(), wrong, child_sizing=SIZING,
            port=SOURCE.port(), current_generation=5,
        )


def test_recursive_measurement_keeps_auto_axes_deferred():
    result = measure_resolved_margin_tree(
        snapshot(), NODES,
        child_sizing=(("child", ChildSizing(Length.auto(), Length.px(20))),),
        port=SOURCE.port(), current_generation=5,
    )
    assert result.deferred == ("child",)
