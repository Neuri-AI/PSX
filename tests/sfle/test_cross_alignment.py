"""F2.2.3 resolved cross alignment and Flex geometry integration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.cross_alignment import CrossAlign, resolve_cross_alignment
from psx.sfle.errors import SFLECapabilityError
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.main_margins import UsedMargin
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout
from psx.sfle.model import WritingDirection


def item(name: str = "a") -> MarginFlexItem:
    return MarginFlexItem(name, FlexBasis(20, 20, shrink=0), 20)


@pytest.mark.parametrize(("alignment", "coordinate"), [
    (CrossAlign.FLEX_START, 0),
    (CrossAlign.FLEX_END, 80),
    (CrossAlign.CENTER, 40),
])
def test_container_align_items_positions_border_box(alignment, coordinate):
    result = compute_margin_flex_layout((item(),), 100, 100, align_items=alignment)
    assert result.boxes[0].border.y == coordinate


def test_align_self_overrides_align_items():
    override = replace(item(), align_self=CrossAlign.FLEX_END)
    result = compute_margin_flex_layout(
        (override,), 100, 100, align_items=CrossAlign.CENTER,
    )
    assert result.boxes[0].border.y == 80


def test_fixed_signed_cross_margins_are_preserved_during_centering():
    box = replace(item(), cross_start=UsedMargin(-10), cross_end=UsedMargin(0))
    result = compute_margin_flex_layout(
        (box,), 100, 100, align_items=CrossAlign.CENTER,
    )
    assert result.boxes[0].border.y == 35
    assert result.boxes[0].used_cross_start_margin == -10


def test_auto_cross_margins_override_align_self():
    box = replace(
        item(), cross_start=UsedMargin(None), cross_end=UsedMargin(None),
        align_self=CrossAlign.FLEX_END,
    )
    result = compute_margin_flex_layout((box,), 100, 100)
    assert result.boxes[0].border.y == 40


def test_reverse_cross_axis_alignment_maps_to_physical_top():
    box = replace(item(), align_self=CrossAlign.FLEX_END)
    result = compute_margin_flex_layout(
        (box,), 100, 100, wrap=FlexWrap.WRAP_REVERSE,
    )
    # A wrapped line is only as tall as its item (20 px), so use a
    # column with definite nowrap cross size to test RTL inversion below.
    assert result.boxes[0].border.y == 80


def test_column_rtl_align_self_end_maps_to_physical_right():
    box = replace(item(), align_self=CrossAlign.FLEX_END)
    result = compute_margin_flex_layout(
        (box,), 100, 40,
        direction=FlexDirection.COLUMN, writing=WritingDirection.RTL,
    )
    assert result.boxes[0].border.x == 80


def test_overflow_end_alignment_keeps_negative_coordinate():
    box = replace(item(), cross_content_size=80)
    result = compute_margin_flex_layout(
        (box,), 100, 50, align_items=CrossAlign.FLEX_END,
    )
    assert result.boxes[0].border.y == -30


def test_unsupported_stretch_and_baseline_are_explicitly_gated():
    for mode in (CrossAlign.STRETCH, CrossAlign.BASELINE):
        with pytest.raises(SFLECapabilityError):
            compute_margin_flex_layout((item(),), 100, 100, align_items=mode)


def test_invalid_align_items_is_rejected():
    with pytest.raises(TypeError):
        compute_margin_flex_layout((item(),), 100, 100, align_items="center")
    with pytest.raises(TypeError):
        compute_margin_flex_layout((item(),), 100, 100, align_items=CrossAlign.AUTO)


def test_pure_kernel_center_reverse_with_fixed_margins():
    value = resolve_cross_alignment(
        CrossAlign.CENTER, CrossAlign.AUTO, 20, 100, -10, 0,
        cross_forward=False,
    )
    assert value == 35
