"""Percentage flex basis: definiteness and content-based fallback."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.errors import SFLECapabilityError
from psx.sfle.intrinsic import IntrinsicFlexInput, MainAxis
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize, IntrinsicSizes
from psx.sfle.percentage_flex_basis import resolve_percentage_flex_basis


@pytest.fixture
def item() -> IntrinsicFlexInput:
    return IntrinsicFlexInput(
        intrinsic=IntrinsicSizes(
            min_content_width=30, max_content_width=120,
            min_content_height=10, max_content_height=70,
            preferred_width=100, preferred_height=60,
        ),
        axis=MainAxis.HORIZONTAL, flex_basis=Length(LengthKind.AUTO),
        preferred_main_size=80,
    )


def test_definite_percent_uses_flex_main_size(item):
    assert resolve_percentage_flex_basis(
        Length.percent(0.5), AvailableSize(200, True), item
    ) == 100


def test_definite_zero_percent_is_zero(item):
    assert resolve_percentage_flex_basis(
        Length.percent(0.0), AvailableSize(200, True), item
    ) == 0


def test_indefinite_zero_percent_uses_content_not_zero(item):
    assert resolve_percentage_flex_basis(
        Length.percent(0.0), AvailableSize(None, False), item
    ) == 120


def test_indefinite_numeric_hint_does_not_make_reference_definite(item):
    assert resolve_percentage_flex_basis(
        Length.percent(0.5), AvailableSize(200, False), item
    ) == 120


def test_indefinite_column_uses_vertical_content(item):
    assert resolve_percentage_flex_basis(
        Length.percent(0.5), AvailableSize(None, False),
        replace(item, axis=MainAxis.VERTICAL),
    ) == 70


def test_indefinite_aspect_ratio_transfer_is_unsupported(item):
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_basis(
            Length.percent(0.5), AvailableSize(None, False),
            replace(item, has_aspect_ratio_transfer=True),
        )


def test_invalid_values_are_rejected(item):
    with pytest.raises(ValueError):
        resolve_percentage_flex_basis(
            Length.percent(-0.1), AvailableSize(200, True), item
        )
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_basis(
            Length.px(20), AvailableSize(200, True), item
        )
