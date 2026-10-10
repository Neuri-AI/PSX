"""End-to-end intrinsic measurement, Flex sizing and constrained remeasurement."""
from psx.sfle.constraint_propagation import ChildSizing
from psx.sfle.flex_math import FlexBasis
from psx.sfle.intrinsic_tree import IntrinsicLeafStyle
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.sfle.native_measurement import NativeMeasurementPort
from psx.sfle.recursive_pipeline import compute_recursive_pipeline


def test_intrinsic_leaf_growth_remeasures_at_allocated_width():
    requested = []
    constraints = LayoutConstraints(AvailableSize(150, True), AvailableSize(80, True))
    snapshot = LayoutInput(
        1, 7, WritingDirection.LTR, constraints,
        (LayoutNode("root", None, "Flex", ()),
         LayoutNode("leaf", "root", "Text", ())), (),
    )
    tree = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0, grow=1, shrink=1), 0)),
    )

    def measure(request: MeasurementRequest) -> MeasuredBox:
        width = request.constraints.width.value
        requested.append((request.node_id, width))
        height = 12 if width is not None and width >= 100 else 24
        return MeasuredBox(
            request.node_id, IntrinsicSizes(20, 60, 8, height, 60, height),
            request.constraints, request.revision,
        )
    result = compute_recursive_pipeline(
        snapshot, tree, child_sizing=((
            "leaf", ChildSizing(Length(LengthKind.AUTO), Length(LengthKind.AUTO)),
        ),), native_port=NativeMeasurementPort(lambda: True, measure),
        intrinsic_leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
        current_generation=7,
    )
    assert result.geometry.boxes[1].content.width == 150
    assert ("leaf", 150) in requested
    assert result.deferred == ()
    assert len(requested) >= 3
