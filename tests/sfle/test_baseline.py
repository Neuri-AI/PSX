"""Horizontal first-baseline alignment with already measured content offsets."""
from __future__ import annotations
from dataclasses import replace
import pytest
from psx.sfle.baseline import BaselineItem, measure_baseline_group, position_baseline_item
from psx.sfle.cross_alignment import CrossAlign
from psx.sfle.errors import SFLECapabilityError
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.main_margins import UsedMargin
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout

def item(name: str, size: float, baseline: float | None) -> MarginFlexItem:
    return MarginFlexItem(
        name, FlexBasis(20,20,shrink=0), size,
        align_self=CrossAlign.BASELINE, baseline_from_cross_start=baseline,
    )

def test_measured_baselines_share_cross_line():
    a, b = item("a",20,15), item("b",30,10)
    result=compute_margin_flex_layout((a,b), 100,100,align_items=CrossAlign.FLEX_START)
    first, second=result.boxes
    assert (first.border.y,second.border.y)==(0,5)
    assert first.border.y+15==second.border.y+10

def test_group_increases_wrapped_line_cross_size():
    a,b=item("a",20,15),item("b",30,10)
    c=replace(item("c",10,8),flex=FlexBasis(80,80,shrink=0))
    result=compute_margin_flex_layout((a,b,c), 100,100,wrap=FlexWrap.WRAP)
    assert result.lines == (("a","b"),("c",))
    assert result.boxes[2].border.y==35

def test_explicit_signed_margins_affect_ascent_and_descent():
    a=replace(item("a",20,15),cross_start=UsedMargin(5))
    b=item("b",30,10)
    result=compute_margin_flex_layout((a,b), 100,100)
    assert result.boxes[0].border.y==5
    assert result.boxes[1].border.y==10
    assert result.boxes[0].border.y+15==result.boxes[1].border.y+10

def test_wrap_reverse_uses_logical_cross_start_measured_baselines():
    a,b=item("a",20,15),item("b",30,10)
    result=compute_margin_flex_layout((a,b),100,100,wrap=FlexWrap.WRAP_REVERSE)
    assert result.boxes[0].border.y==80
    assert result.boxes[1].border.y==65

def test_missing_metric_is_rejected():
    with pytest.raises(SFLECapabilityError):
        compute_margin_flex_layout((item("a",20,None),),100,100)

def test_column_baseline_requires_orthogonal_metric():
    with pytest.raises(SFLECapabilityError):
        compute_margin_flex_layout((item("a",20,10),),100,100,
                                   direction=FlexDirection.COLUMN)

def test_auto_cross_margin_takes_precedence_without_metric():
    a=replace(item("a",20,None),cross_start=UsedMargin(None),
              cross_end=UsedMargin(None))
    result=compute_margin_flex_layout((a,),100,100)
    assert result.boxes[0].border.y==40

def test_baseline_values_must_fit_content():
    with pytest.raises(ValueError):
        item("x",10,11)
    with pytest.raises(ValueError):
        BaselineItem(10,0,0,-1)

def test_pure_group_uses_max_ascent_and_descent():
    a=BaselineItem(20,0,0,15)
    b=BaselineItem(30,0,0,10)
    group=measure_baseline_group((a,b))
    assert group.extent==35
    assert position_baseline_item(b,group,35)==5
    assert position_baseline_item(b,group,35,cross_forward=False)==0
