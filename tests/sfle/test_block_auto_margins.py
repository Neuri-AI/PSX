"""Block-flow horizontal auto margins use remaining inline space."""

from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
    WritingDirection,
)
from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot


def layout(width, item_width, *, left="auto", right="auto", top=0, bottom=0):
    constraints = LayoutConstraints(
        AvailableSize(width, True), AvailableSize(400, True)
    )
    nodes = (
        LayoutNode("root", None, "div", ()),
        LayoutNode("item", "root", "div", (
            ("layout_width", Length.px(item_width)),
            ("layout_margin_left", left),
            ("layout_margin_right", right),
            ("layout_margin_top", top),
            ("layout_margin_bottom", bottom),
        )),
    )
    return dict(compute_measured_block_snapshot(LayoutInput(
        1, 1, WritingDirection.LTR, constraints, nodes, (),
    )).boxes)["item"]


def test_two_auto_margins_center_fixed_width_block():
    for width in (200, 400, 800):
        box = layout(width, 100)
        assert box.border.x == (width - 100) / 2
        assert box.margin.x == 0
        assert box.margin.width == width


def test_single_auto_side_absorbs_remaining_space():
    assert layout(300, 100, left="auto", right=Length.px(20)).border.x == 180
    assert layout(300, 100, left=Length.px(20), right="auto").border.x == 20


def test_vertical_auto_margins_are_zero_in_normal_block_flow():
    box = layout(300, 100, top="auto", bottom="auto")
    assert box.border.y == 0
    assert box.margin.y == 0
