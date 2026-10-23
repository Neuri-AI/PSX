"""Measured block snapshot must retain real intrinsic dimensions and fail closed."""
import pytest

from psx.sfle.errors import SFLECapabilityError
from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def snapshot(*, measured=True, nested=False):
    constraints = LayoutConstraints(
        AvailableSize(240.0, True), AvailableSize(400.0, True)
    )
    nodes = (
        LayoutNode("root", None, "div", ()),
        LayoutNode("button", "root", "Button", ()),
        LayoutNode("text", "button" if nested else "root", "Text", ()),
    )
    data = (
        MeasuredBox("button", IntrinsicSizes(40, 40, 12, 12, 40, 12), constraints, 1),
        MeasuredBox("text", IntrinsicSizes(100, 100, 30, 30, 100, 30), constraints, 1),
    ) if measured else ()
    return LayoutInput(1, 7, WritingDirection.LTR, constraints, nodes, data)


def test_native_block_flow_uses_measured_leaf_heights():
    result = compute_measured_block_snapshot(snapshot())
    rectangles = dict(result.boxes)
    assert result.generation == 7
    assert rectangles["root"].border.height == 30
    assert rectangles["button"].border == rectangles["button"].content
    assert rectangles["button"].border.width == 40
    assert rectangles["text"].border.x == 40
    assert rectangles["text"].border.y == 0
    assert rectangles["text"].border.height == 30


def test_unmeasured_native_leaf_is_not_replaced_with_fake_zero():
    with pytest.raises(SFLECapabilityError, match="missing intrinsic"):
        compute_measured_block_snapshot(snapshot(measured=False))


def test_nested_native_tree_needs_real_nested_formatter():
    with pytest.raises(SFLECapabilityError, match="Nested Block/Inline"):
        compute_measured_block_snapshot(snapshot(nested=True))


def test_inline_atoms_share_a_line_and_align_native_baselines():
    initial = snapshot()
    nodes = (
        LayoutNode("root", None, "div", (("display", "inline"),)),
        initial.nodes[1],
        initial.nodes[2],
    )
    computed = compute_measured_block_snapshot(LayoutInput(
        1, initial.generation, initial.direction,
        initial.constraints, nodes, initial.measurements,
    ))
    rects = dict(computed.boxes)
    assert rects["button"].border.x == 0
    assert rects["text"].border.x == 40
    assert rects["button"].border.y == 18
    assert rects["text"].border.y == 0
    assert rects["button"].border.width == 40


def test_inline_atoms_wrap_when_native_measurements_exceed_viewport():
    initial = snapshot()
    constrained = LayoutConstraints(
        AvailableSize(75, True), AvailableSize(400, True),
    )
    nodes = (
        LayoutNode("root", None, "div", (("display", "inline"),)),
        initial.nodes[1],
        initial.nodes[2],
    )
    result = compute_measured_block_snapshot(LayoutInput(
        1, initial.generation, initial.direction, constrained,
        nodes, initial.measurements,
    ))
    rects = dict(result.boxes)
    assert rects["button"].border.x == 0
    assert rects["text"].border.x == 0
    assert rects["text"].border.y == 12


def test_fractional_native_metrics_land_on_fixed_point_grid():
    initial = snapshot()
    measured = (
        MeasuredBox(
            "button",
            IntrinsicSizes(39.3, 39.3, 12.3, 12.3, 39.3, 12.3, 9.1),
            initial.constraints, 1,
        ),
        MeasuredBox(
            "text",
            IntrinsicSizes(90.7, 90.7, 30.7, 30.7, 90.7, 30.7, 24.2),
            initial.constraints, 1,
        ),
    )
    updated = LayoutInput(
        initial.schema_version, initial.generation, initial.direction,
        initial.constraints, initial.nodes, measured,
    )
    result = compute_measured_block_snapshot(updated)
    for _, box in result.boxes:
        for axis in ("x", "y", "width", "height"):
            value = getattr(box.border, axis)
            assert value * 64 == round(value * 64)
    assert dict(result.boxes)["text"].border.y == round(12.3 * 64) / 64
