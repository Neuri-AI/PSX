"""Nested Grid widths follow the content box of surrounding HTML-like blocks."""
from psx.sfle.grid_native_composition import nested_flow_grid_width
from psx.sfle.lengths import Length
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection


def _snapshot(*nodes):
    constraints = LayoutConstraints(AvailableSize(1000, True), AvailableSize(None, False))
    return LayoutInput(1, 1, WritingDirection.LTR, constraints, tuple(nodes), ())


def _node(identity, parent, component, **style):
    return LayoutNode(identity, parent, component, tuple(sorted(style.items())))


def test_grid_inside_padded_container_uses_container_content_width():
    layout = _snapshot(
        _node("root", None, "div"),
        _node("container", "root", "div",
              layout_padding_left=Length.px(16),
              layout_padding_right=Length.px(16)),
        _node("cards", "container", "Grid"),
    )
    assert nested_flow_grid_width(layout, "cards", 1000) == 968


def test_grid_inside_nested_padded_and_bordered_blocks_respects_all_edges():
    layout = _snapshot(
        _node("root", None, "div", layout_padding_left=Length.px(8)),
        _node("container", "root", "div",
              layout_padding_left=Length.px(16),
              layout_padding_right=Length.px(16),
              layout_border_left=Length.px(1),
              layout_border_right=Length.px(1)),
        _node("cards", "container", "Grid"),
    )
    assert nested_flow_grid_width(layout, "cards", 1000) == 958


def test_grid_under_explicit_content_width_and_percentage_padding():
    layout = _snapshot(
        _node("root", None, "div"),
        _node("container", "root", "div", layout_width=Length.px(600)),
        _node("inner", "container", "div",
              layout_padding_left=Length.percent(0.1),
              layout_padding_right=Length.percent(0.1)),
        _node("cards", "inner", "Grid"),
    )
    assert nested_flow_grid_width(layout, "cards", 1000) == 480
