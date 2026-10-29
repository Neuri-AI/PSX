"""Measured block snapshot must retain real intrinsic dimensions and fail closed."""
import pytest

from psx.sfle.errors import SFLECapabilityError
from psx.sfle.fixed_point import LayoutUnit, nearest_layout_px
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


@pytest.mark.parametrize("value", [
    0, 0.1, -0.1, 0.5 / 64, -0.5 / 64,
    1.5 / 64, -1.5 / 64, 2.5 / 64, -2.5 / 64,
    19.3, -19.3, 1000.234, -1000.234,
    (2**31 - 1) / 64, -(2**31) / 64,
    2**31, -(2**31),
])
def test_fast_block_rounding_is_bit_identical_to_blink_layout_unit(value):
    assert nearest_layout_px(value) == LayoutUnit.from_nearest(value).to_px()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_fast_block_rounding_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="NaN and infinity"):
        nearest_layout_px(value)


def test_native_block_flow_uses_measured_leaf_heights():
    result = compute_measured_block_snapshot(snapshot())
    rectangles = dict(result.boxes)
    assert result.generation == 7
    assert rectangles["root"].border.height == 42
    assert rectangles["button"].border == rectangles["button"].content
    assert rectangles["button"].border.width == 40
    assert rectangles["text"].border.x == 0
    assert rectangles["text"].border.width == 240
    assert rectangles["text"].border.y == 12
    assert rectangles["text"].border.height == 30


def test_zero_edge_native_boxes_reuse_already_quantized_geometry():
    result = compute_measured_block_snapshot(snapshot())
    for box in dict(result.boxes).values():
        assert box.content is box.padding
        assert box.padding is box.border
        assert box.border is box.margin


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


def test_native_input_and_button_keep_intrinsic_width_under_block_parent():
    base = snapshot()
    nodes = (
        LayoutNode("root", None, "div", ()),
        LayoutNode("input", "root", "Input", ()),
        LayoutNode("button", "root", "Button", ()),
    )
    measures = (
        MeasuredBox("input", IntrinsicSizes(185, 185, 22, 22, 185, 22), base.constraints, 1),
        MeasuredBox("button", IntrinsicSizes(66, 66, 22, 22, 66, 22), base.constraints, 1),
    )
    boxes = dict(compute_measured_block_snapshot(LayoutInput(
        1, base.generation, base.direction, base.constraints, nodes, measures,
    )).boxes)
    assert boxes["input"].border.width == 185
    assert boxes["button"].border.width == 66
    assert boxes["button"].border.y == 22
    assert boxes["root"].border.width == 240
    assert boxes["root"].border.height == 44


def test_auto_height_native_fits_padded_max_height_content_box():
    from psx.sfle.lengths import Length
    initial = snapshot()
    nodes = (
        LayoutNode("card", None, "div", (
            ("layout_max_height", Length.px(250)),
            ("layout_padding_top", Length.px(16)),
            ("layout_padding_bottom", Length.px(16)),
            ("layout_padding_left", Length.px(16)),
            ("layout_padding_right", Length.px(16)),
            ("layout_border_top", Length.px(1)),
            ("layout_border_bottom", Length.px(1)),
            ("layout_border_left", Length.px(1)),
            ("layout_border_right", Length.px(1)),
        )),
        LayoutNode("chart", "card", "Native", ()),
    )
    measures = (
        MeasuredBox("chart", IntrinsicSizes(0, 700, 250, 480, 640, 480),
                    initial.constraints, 1),
    )
    boxes = dict(compute_measured_block_snapshot(LayoutInput(
        1, initial.generation, initial.direction, initial.constraints,
        nodes, measures,
    )).boxes)
    assert boxes["card"].border.height == 284
    assert boxes["chart"].border.y == 17
    assert boxes["chart"].border.height == 250
    assert boxes["chart"].border.x == 17


def test_explicit_native_height_remains_authoritative_even_with_parent_max():
    from psx.sfle.lengths import Length
    initial = snapshot()
    nodes = (
        LayoutNode("card", None, "div", (("layout_max_height", Length.px(250)),)),
        LayoutNode("chart", "card", "Native", (("layout_height", Length.px(300)),)),
    )
    measures = (
        MeasuredBox("chart", IntrinsicSizes(0, 700, 250, 480, 640, 480),
                    initial.constraints, 1),
    )
    boxes = dict(compute_measured_block_snapshot(LayoutInput(
        1, initial.generation, initial.direction, initial.constraints,
        nodes, measures,
    )).boxes)
    assert boxes["chart"].border.height == 300
    assert boxes["card"].content.height == 250
