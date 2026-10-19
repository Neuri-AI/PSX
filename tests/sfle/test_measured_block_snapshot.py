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
    assert rectangles["root"].border.height == 400
    assert rectangles["button"].border == rectangles["button"].content
    assert rectangles["button"].border.width == 240
    assert rectangles["text"].border.y == 12
    assert rectangles["text"].border.height == 30


def test_unmeasured_native_leaf_is_not_replaced_with_fake_zero():
    with pytest.raises(SFLECapabilityError, match="missing intrinsic"):
        compute_measured_block_snapshot(snapshot(measured=False))


def test_nested_native_tree_needs_real_nested_formatter():
    with pytest.raises(SFLECapabilityError, match="Nested Block/Inline"):
        compute_measured_block_snapshot(snapshot(nested=True))
