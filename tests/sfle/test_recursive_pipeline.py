"""End-to-end intrinsic measurement, Flex sizing and constrained remeasurement."""
from psx.layout.fallback.constraint_propagation import ChildSizing
from psx.layout.fallback.flex_math import FlexBasis
from psx.layout.fallback.intrinsic_tree import IntrinsicLeafStyle
from psx.layout.contracts.lengths import Length, LengthKind
from psx.layout.fallback.margin_flex_pipeline import MarginFlexItem
from psx.layout.fallback.margin_tree import MarginTreeNode
from psx.layout.fallback.measurement_plan import MeasurementRequest
from psx.layout.contracts.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.layout.runtime.native_measurement import NativeMeasurementPort
from psx.layout.runtime.recursive_pipeline import compute_recursive_pipeline


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


def test_native_lifecycle_commits_converged_intrinsic_geometry():
    from psx.layout.runtime.native_lifecycle import NativeLayoutLifecycle, layout_and_commit

    constraints = LayoutConstraints(AvailableSize(150, True), AvailableSize(80, True))
    snapshot = LayoutInput(
        1, 9, WritingDirection.LTR, constraints,
        (LayoutNode("root", None, "Flex", ()),
         LayoutNode("leaf", "root", "Text", ())), (),
    )
    tree = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("leaf", "root", 0, 0,
            MarginFlexItem("leaf", FlexBasis(0, 0, grow=1, shrink=1), 0)),
    )
    committed = []

    def measured(request):
        width = request.constraints.width.value
        height = 12 if width is not None and width >= 100 else 24
        return MeasuredBox(
            request.node_id, IntrinsicSizes(20, 60, 8, height, 60, height),
            request.constraints, request.revision,
        )

    lifecycle = NativeLayoutLifecycle(
        lambda: 9, NativeMeasurementPort(lambda: True, measured), committed.append,
    )
    output = layout_and_commit(
        snapshot, tree, lifecycle,
        child_sizing=(("leaf", ChildSizing(
            Length(LengthKind.AUTO), Length(LengthKind.AUTO),
        )),),
        intrinsic_leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
    )
    assert committed == [output]
    assert output.geometry.boxes[1].content.width == 150
    assert output.geometry.boxes[1].content.height == 12


def test_indefinite_root_reference_fails_closed():
    import pytest
    from psx.layout.contracts.errors import SFLEError

    constraints = LayoutConstraints(AvailableSize(150, True), AvailableSize(None, False))
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
    def measure(request):
        return MeasuredBox(
            request.node_id, IntrinsicSizes(20, 60, 8, 24, 60, 24),
            request.constraints, request.revision,
        )
    with pytest.raises(SFLEError, match="No sizing rule for deferred CSS node"):
        compute_recursive_pipeline(
            snapshot, tree,
            child_sizing=(("leaf", ChildSizing(
                Length(LengthKind.AUTO), Length.percent(0.5),
            )),),
            native_port=NativeMeasurementPort(lambda: True, measure),
            intrinsic_leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
            current_generation=7,
        )


def test_auto_cross_container_resolves_before_final_commit():
    from psx.layout.fallback.auto_cross_tree import AutoCrossSize
    from psx.layout.runtime.native_lifecycle import NativeLayoutLifecycle, layout_and_commit
    constraints = LayoutConstraints(AvailableSize(150, True), AvailableSize(80, True))
    snapshot = LayoutInput(
        1, 11, WritingDirection.LTR, constraints,
        (
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("container", "root", "Flex", ()),
            LayoutNode("leaf", "container", "Text", ()),
        ), (),
    )
    nodes = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("container", "root", 20, 0,
            MarginFlexItem("container", FlexBasis(20, 20, grow=0, shrink=0), 0)),
        MarginTreeNode("leaf", "container", 20, 18,
            MarginFlexItem("leaf", FlexBasis(20, 20, grow=0, shrink=0), 18)),
    )
    commits = []

    def measure(request):
        return MeasuredBox(
            request.node_id,
            IntrinsicSizes(10, 20, 10, 18, 20, 18),
            request.constraints, request.revision,
        )

    lifecycle = NativeLayoutLifecycle(
        lambda: 11, NativeMeasurementPort(lambda: True, measure), commits.append,
    )
    result = layout_and_commit(
        snapshot, nodes, lifecycle,
        child_sizing=(
            ("container", ChildSizing(Length.px(20), Length(LengthKind.AUTO))),
            ("leaf", ChildSizing(Length.px(20), Length.px(18))),
        ),
        auto_cross=(AutoCrossSize("container"),),
    )
    assert result.geometry.boxes[1].content.height == 18
    assert result.deferred == ()
    assert commits == [result]
