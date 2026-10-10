"""F2.2.2: CSS cyclic percentage gap and definite box-sizing boundaries."""

from __future__ import annotations

import pytest

from psx.sfle.errors import DiagnosticCode, SFLECapabilityError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize
from psx.sfle.percentage_box_sizing import (
    BoxSizing, GapPhase, normalize_box_size, resolve_percentage_gap,
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
