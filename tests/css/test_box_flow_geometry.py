"""Cinnamon flow must compute distinct boxes and account for outer flow dimensions."""
from psx.sfle.lengths import Length
from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _request(*nodes: LayoutNode) -> LayoutInput:
    constraints = LayoutConstraints(AvailableSize(200, True), AvailableSize(120, True))
    measures = tuple(
        MeasuredBox(node.node_id, IntrinsicSizes(20, 20, 10, 10, 20, 10), constraints, 1)
        for node in nodes if node.component == "Button"
    )
    return LayoutInput(1, 1, WritingDirection.LTR, constraints, tuple(nodes), measures)


def _node(name, parent, component, **props):
    return LayoutNode(name, parent, component, tuple(sorted(props.items())))


def test_margin_padding_and_border_shift_content_and_next_sibling():
    root = _node("root", None, "div", display="block")
    first = _node(
        "first", "root", "div", display="block",
        layout_padding_top=Length.px(10), layout_padding_right=Length.px(10),
        layout_padding_bottom=Length.px(10), layout_padding_left=Length.px(10),
        layout_border_top=Length.px(2), layout_border_right=Length.px(2),
        layout_border_bottom=Length.px(2), layout_border_left=Length.px(2),
        layout_margin_top=Length.px(3), layout_margin_right=Length.px(3),
        layout_margin_bottom=Length.px(3), layout_margin_left=Length.px(3),
    )
    leaf = _node("leaf", "first", "Button", layout_width=Length.px(20))
    second = _node("second", "root", "Button", layout_margin_top=Length.px(5))
    output = dict(compute_measured_block_snapshot(_request(root, first, leaf, second)).boxes)
    assert output["first"].margin.x == 0
    assert output["first"].border.x == 3
    assert output["first"].padding.x == 5
    assert output["first"].content.x == 15
    assert output["first"].content.width == 170
    assert output["leaf"].content.x == 15
    assert output["leaf"].content.y == 15
    assert output["first"].margin.height == 40
    assert output["second"].content.y == 45
    assert output["root"].border.width == 200


def test_min_max_constrain_used_content_width_and_height():
    root = _node("root", None, "div", display="block")
    child = _node(
        "child", "root", "Button",
        layout_width=Length.px(190),
        layout_height=Length.px(80),
        layout_min_width=Length.px(110),
        layout_max_width=Length.px(100),
        layout_min_height=Length.px(15),
        layout_max_height=Length.px(40),
    )
    output = dict(compute_measured_block_snapshot(_request(root, child)).boxes)
    assert output["child"].content.width == 110
    assert output["child"].content.height == 40


def test_percentages_resolve_against_parent_containing_width():
    root = _node("root", None, "div", display="block")
    child = _node(
        "child", "root", "Button",
        layout_width=Length.percent(.5),
        layout_padding_left=Length.percent(.1),
        layout_margin_top=Length.percent(.05),
    )
    output = dict(compute_measured_block_snapshot(_request(root, child)).boxes)
    assert output["child"].content.width == 100
    assert output["child"].border.x == 0
    assert output["child"].content.x == 20
    assert output["child"].content.y == 10



def test_percent_height_uses_definite_parent_height_not_viewport_width():
    root = _node("root", None, "div", display="block")
    middle = _node("middle", "root", "div", display="block", layout_height=Length.px(60))
    child = _node("child", "middle", "Button", layout_height=Length.percent(.5))
    result = dict(compute_measured_block_snapshot(_request(root, middle, child)).boxes)
    assert result["child"].content.height == 30


def test_percent_height_in_auto_block_falls_back_to_intrinsic_height():
    root = _node("root", None, "div", display="block")
    middle = _node("middle", "root", "div", display="block")
    child = _node("child", "middle", "Button", layout_height=Length.percent(.5))
    result = dict(compute_measured_block_snapshot(_request(root, middle, child)).boxes)
    assert result["child"].content.height == 10


def test_percentage_width_uses_parent_resolved_width():
    root = _node('root', None, 'div', display='block')
    middle = _node('middle', 'root', 'div', display='block', layout_width=Length.px(150), layout_padding_left=Length.px(10))
    leaf = _node('leaf', 'middle', 'Button', layout_width=Length.percent(.5))
    boxes = dict(compute_measured_block_snapshot(_request(root, middle, leaf)).boxes)
    assert boxes['middle'].content.width == 150
    assert boxes['leaf'].content.width == 75
    assert boxes['leaf'].content.x == 10
