"""F2.2.2: CSS cyclic percentage gap and definite box-sizing boundaries."""

from __future__ import annotations

import pytest

from psx.sfle.errors import DiagnosticCode, SFLECapabilityError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize
from psx.sfle.percentage_box_sizing import (
    BoxSizing, GapPhase, normalize_box_size, normalize_flex_box_basis, resolve_percentage_gap,
)


def test_definite_gap_percent_uses_reference_axis():
    assert resolve_percentage_gap(
        Length.percent(0.25), AvailableSize(80, True), phase=GapPhase.USED_LAYOUT
    ) == 20


def test_indefinite_gap_intrinsic_contribution_is_zero_not_used_value():
    ref = AvailableSize(None, False)
    assert resolve_percentage_gap(
        Length.percent(0.1), ref, phase=GapPhase.INTRINSIC_CONTRIBUTION
    ) == 0
    with pytest.raises(SFLECapabilityError) as exc:
        resolve_percentage_gap(
            Length.percent(0.1), ref, phase=GapPhase.USED_LAYOUT
        )
    assert exc.value.code == DiagnosticCode.UNSUPPORTED_FEATURE


def test_available_hint_is_not_a_definite_used_size():
    hint = AvailableSize(400, False)
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_gap(
            Length.percent(0.1), hint, phase=GapPhase.USED_LAYOUT
        )


@pytest.mark.parametrize(
    ("sizing", "expected_content", "expected_border"),
    [
        (BoxSizing.CONTENT_BOX, 100, 130),
        (BoxSizing.BORDER_BOX, 70, 100),
    ],
)
def test_content_and_border_box(sizing, expected_content, expected_border):
    result = normalize_box_size(100, 30, sizing)
    assert (result.content, result.border_box) == (
        expected_content, expected_border
    )


def test_border_box_smaller_than_padding_border_has_zero_content():
    result = normalize_box_size(10, 20, BoxSizing.BORDER_BOX)
    assert result.content == 0
    assert result.border_box == 20


def test_definite_zero_is_distinct_from_indefinite():
    result = resolve_percentage_gap(
        Length.percent(0.4), AvailableSize(0, True), phase=GapPhase.USED_LAYOUT
    )
    assert result == 0


def test_negative_gap_and_invalid_keyword_rejected():
    with pytest.raises(ValueError):
        resolve_percentage_gap(
            Length.percent(-0.1), AvailableSize(100, True), phase=GapPhase.USED_LAYOUT
        )
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_gap(
            Length(LengthKind.AUTO), AvailableSize(100, True), phase=GapPhase.USED_LAYOUT
        )
    with pytest.raises(ValueError):
        normalize_box_size(5, -2, BoxSizing.BORDER_BOX)


def test_border_box_flex_constraints_normalized_to_content_units():
    result = normalize_flex_box_basis(
        100, 30, BoxSizing.BORDER_BOX, min_size=80, max_size=90, grow=1
    )
    assert result.basis == 70
    assert result.min_size == 50
    assert result.max_size == 60
    assert result.hypothetical == 60


def test_content_box_flex_constraints_keep_specified_sizes():
    result = normalize_flex_box_basis(
        100, 30, BoxSizing.CONTENT_BOX, min_size=80, max_size=90
    )
    assert (result.basis, result.min_size, result.max_size, result.hypothetical) == (
        100, 80, 90, 90
    )


def test_minimum_wins_when_maximum_is_smaller():
    result = normalize_flex_box_basis(
        100, 30, BoxSizing.BORDER_BOX, min_size=90, max_size=50
    )
    assert (result.min_size, result.max_size, result.hypothetical) == (60, 60, 60)


def test_border_box_fixed_edges_never_produce_negative_content():
    result = normalize_flex_box_basis(
        10, 20, BoxSizing.BORDER_BOX, min_size=0, max_size=10
    )
    assert (result.basis, result.min_size, result.max_size) == (0, 0, 0)


def test_box_sizing_rejects_bad_constraints():
    with pytest.raises(ValueError):
        normalize_flex_box_basis(-1, 10, BoxSizing.BORDER_BOX)
    with pytest.raises(ValueError):
        normalize_flex_box_basis(10, 2, BoxSizing.BORDER_BOX, max_size=-1)


def test_normalized_flex_basis_feeds_signed_margin_pipeline():
    from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
    from psx.sfle.main_margins import UsedMargin
    from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout

    flex = normalize_flex_box_basis(
        100, 30, BoxSizing.BORDER_BOX, min_size=80, max_size=90
    )
    result = compute_margin_flex_layout(
        (MarginFlexItem(
            node_id="a", flex=flex, cross_content_size=10,
            edges=UsedBoxEdges(padding=UsedEdges(left=15, right=15)),
            main_start=UsedMargin(0), main_end=UsedMargin(0),
        ),),
        width=200, height=40,
    )
    assert result.boxes[0].content.width == 60
    assert result.boxes[0].border.width == 90
