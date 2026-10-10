"""Resolved CSS edge contributions are included before Flexbox line sizing."""

from __future__ import annotations

import pytest

from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
from psx.sfle.edge_pipeline import ResolvedEdgeItem, compute_edge_layout
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.model import WritingDirection


def item(name: str, size: float, *, grow: float = 0, edges: UsedBoxEdges = UsedBoxEdges()):
    return ResolvedEdgeItem(name, FlexBasis(size, size, grow=grow), 10, edges)


def test_fixed_edges_reduce_space_for_flex_content_not_outer_boxes():
    edges = UsedBoxEdges(
        margin=UsedEdges(left=5, right=5),
        border=UsedEdges(left=1, right=1),
        padding=UsedEdges(left=5, right=5),
    )
    result = compute_edge_layout(
        (item("a", 20, grow=1, edges=edges), item("b", 20, grow=1, edges=edges)),
        100, 30,
    )
    boxes = dict(result.boxes)
    assert result.lines == (("a", "b"),)
    assert boxes["a"].margin.width == 50
    assert boxes["a"].content.width == 28
    assert boxes["a"].content.x == 11
    assert boxes["b"].margin.x == 50
    assert boxes["b"].content.x == 61
    assert boxes["b"].content.width == 28


def test_wrapping_uses_outer_hypothetical_sizes_not_content_size():
    edges = UsedBoxEdges(padding=UsedEdges(left=5, right=5))
    result = compute_edge_layout(
        (item("a", 45, grow=1, edges=edges), item("b", 45, grow=1, edges=edges)),
        100, 50, wrap=FlexWrap.WRAP,
    )
    assert result.lines == (("a",), ("b",))
    assert tuple(box.margin.width for _, box in result.boxes) == (100, 100)


def test_rtl_placement_moves_full_margin_box_and_preserves_content_offset():
    edges = UsedBoxEdges(
        margin=UsedEdges(left=2, right=3),
        padding=UsedEdges(left=5, right=1),
    )
    result = compute_edge_layout(
        (item("a", 20, edges=edges),), 100, 30,
        direction=FlexDirection.ROW, writing=WritingDirection.RTL,
    )
    box = result.boxes[0][1]
    assert box.margin.x == 69
    assert box.border.x == 71
    assert box.content.x == 76
    assert box.content.width == 20


def test_nonzero_border_and_padding_along_cross_axis():
    edges = UsedBoxEdges(
        border=UsedEdges(top=1, bottom=2),
        padding=UsedEdges(top=3, bottom=4),
    )
    result = compute_edge_layout((item("x", 20, edges=edges),), 100, 100)
    box = result.boxes[0][1]
    assert box.margin.height == 20
    assert box.content.y == 4
    assert box.content.height == 10


def test_negative_margins_explicitly_rejected_in_this_subset():
    with pytest.raises(ValueError, match="Signed margins"):
        item("a", 20, edges=UsedBoxEdges(margin=UsedEdges(left=-1)))


def test_fixed_edges_larger_than_container_overflow_instead_of_disappearing():
    edges = UsedBoxEdges(padding=UsedEdges(left=15, right=15))
    result = compute_edge_layout((item("a", 20, edges=edges),), 10, 30)
    box = result.boxes[0][1]
    assert box.margin.width == 50
    assert box.content.width == 20
