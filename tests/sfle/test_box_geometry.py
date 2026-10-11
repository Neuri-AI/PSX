"""Focused used CSS box geometry tests (no native renderer)."""

from __future__ import annotations

import pytest

from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges, used_box_rect
from psx.sfle.model import Rect


def test_content_padding_border_margin_rectangles():
    margin_box = Rect(10, 20, 110, 60)
    box = used_box_rect(
        margin_box,
        UsedBoxEdges(
            margin=UsedEdges(2, 3, 4, 5),
            border=UsedEdges(1, 2, 3, 4),
            padding=UsedEdges(6, 7, 8, 9),
        ),
    )
    assert box.margin == margin_box
    assert box.border == Rect(15, 22, 102, 54)
    assert box.padding == Rect(19, 23, 96, 50)
    assert box.content == Rect(28, 29, 80, 36)


def test_negative_margin_still_preserves_physical_edge_geometry():
    result = used_box_rect(
        Rect(10, 10, 100, 40),
        UsedBoxEdges(margin=UsedEdges(left=-5, right=10)),
    )
    assert result.border == Rect(5, 10, 95, 40)
    assert result.content == result.border


def test_zero_edges_do_not_change_rectangles():
    outer = Rect(0, 0, 100, 50)
    result = used_box_rect(outer, UsedBoxEdges())
    assert result.content == result.padding == result.border == result.margin == outer


@pytest.mark.parametrize("edges", [
    UsedBoxEdges(padding=UsedEdges(left=101)),
    UsedBoxEdges(border=UsedEdges(top=51)),
])
def test_reject_impossible_used_box_edges(edges):
    with pytest.raises(ValueError):
        used_box_rect(Rect(0, 0, 100, 50), edges)


def test_reject_negative_border_and_padding():
    with pytest.raises(ValueError):
        UsedBoxEdges(border=UsedEdges(left=-1))
    with pytest.raises(ValueError):
        UsedBoxEdges(padding=UsedEdges(bottom=-1))
