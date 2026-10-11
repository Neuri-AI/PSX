"""F2.2.3 resolved item stretching, bounds, and auto-margin priority."""
from __future__ import annotations
from dataclasses import replace
import pytest
from psx.sfle.cross_stretch import resolve_cross_stretch
from psx.sfle.cross_alignment import CrossAlign
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.main_margins import UsedMargin
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout
from psx.sfle.model import WritingDirection
from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges

def item() -> MarginFlexItem:
    return MarginFlexItem("a", FlexBasis(20, 20, shrink=0), 10, cross_size_auto=True)

def test_auto_stretch_fills_resolved_nowrap_line():
    b = compute_margin_flex_layout((item(),), 100, 100, align_items=CrossAlign.STRETCH).boxes[0]
    assert (b.border.y, b.border.height, b.content.height) == (0, 100, 100)

def test_explicit_cross_size_is_not_stretched():
    b = compute_margin_flex_layout((replace(item(), cross_size_auto=False),), 100, 100,
                                   align_items=CrossAlign.STRETCH).boxes[0]
    assert b.border.height == 10

def test_item_stretch_override_and_auto_inheritance():
    first = replace(item(), align_self=CrossAlign.STRETCH)
    b = compute_margin_flex_layout((first,), 100, 80, align_items=CrossAlign.FLEX_END).boxes[0]
    assert b.border.height == 80

def test_item_override_disables_container_stretch():
    first = replace(item(), align_self=CrossAlign.CENTER)
    b = compute_margin_flex_layout((first,), 100, 80, align_items=CrossAlign.STRETCH).boxes[0]
    assert (b.border.y, b.border.height) == (35, 10)

def test_auto_cross_margins_prevent_stretch():
    first = replace(item(), cross_start=UsedMargin(None), cross_end=UsedMargin(None))
    b = compute_margin_flex_layout((first,), 100, 100, align_items=CrossAlign.STRETCH).boxes[0]
    assert (b.border.y, b.border.height) == (45, 10)

def test_stretch_preserves_padding_border_and_signed_margins():
    first = replace(item(),
        edges=UsedBoxEdges(padding=UsedEdges(top=5,bottom=5)),
        cross_start=UsedMargin(-5), cross_end=UsedMargin(10))
    b = compute_margin_flex_layout((first,), 100, 100, align_items=CrossAlign.STRETCH).boxes[0]
    assert (b.border.y, b.border.height, b.content.height) == (-5, 95, 85)

def test_definite_max_clamps_stretched_auto_cross_size():
    first = replace(item(), max_cross_content_size=30)
    b = compute_margin_flex_layout((first,), 100, 100, align_items=CrossAlign.STRETCH).boxes[0]
    assert b.border.height == 30

def test_definite_minimum_can_force_overflow():
    first = replace(item(), min_cross_content_size=120)
    b = compute_margin_flex_layout((first,), 100, 100, align_items=CrossAlign.STRETCH).boxes[0]
    assert b.border.height == 120

def test_stretch_uses_expanded_align_content_line():
    a=replace(item(), node_id="a")
    b=replace(item(), node_id="b")
    from psx.sfle.align_content import AlignContent
    out=compute_margin_flex_layout((a,b), 30, 100, wrap=FlexWrap.WRAP,
        align_items=CrossAlign.STRETCH, align_content=AlignContent.STRETCH, cross_gap=10)
    assert [box.border.height for box in out.boxes] == [45,45]
    assert [box.border.y for box in out.boxes] == [0,55]

def test_column_rtl_stretch_expands_width():
    b=compute_margin_flex_layout((item(),), 100, 40, direction=FlexDirection.COLUMN,
        writing=WritingDirection.RTL, align_items=CrossAlign.STRETCH).boxes[0]
    assert (b.border.x,b.border.width)==(0,100)

def test_pure_stretch_floor_and_conflicting_limits():
    used=resolve_cross_stretch(10, 20, 0, 0, min_content_size=5, max_content_size=1)
    assert (used.content_size,used.border_size)==(5,25)

def test_invalid_cross_bounds_rejected():
    with pytest.raises(ValueError):
        replace(item(), min_cross_content_size=-1)
    with pytest.raises(ValueError):
        resolve_cross_stretch(10,-1,0,0)
