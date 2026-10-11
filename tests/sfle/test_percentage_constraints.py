"""Typed, property-aware percentage-to-FlexBasis integration contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.errors import SFLECapabilityError
from psx.sfle.intrinsic import IntrinsicFlexInput, MainAxis
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize, IntrinsicSizes
from psx.sfle.percentage_box_sizing import BoxSizing
from psx.sfle.percentage_constraints import (
    PercentageFlexConstraints, resolve_percentage_flex_constraints,
)


@pytest.fixture
def sample() -> PercentageFlexConstraints:
    return PercentageFlexConstraints(
        basis=Length.percent(0.5),
        minimum=Length.percent(0.25),
        maximum=Length.percent(0.75),
        containing_inline_size=AvailableSize(300, True),
        containing_main_axis_size=AvailableSize(200, True),
        flex_container_main_size=AvailableSize(200, True),
        padding_border=20, sizing=BoxSizing.BORDER_BOX, grow=1,
    )


def test_definite_percent_min_max_and_basis_convert_to_content_box(sample):
    result = resolve_percentage_flex_constraints(sample)
    assert (result.basis, result.min_size, result.max_size, result.hypothetical) == (
        80, 30, 130, 80
    )


def test_percent_min_and_max_use_containing_block_not_flex_container(sample):
    result = resolve_percentage_flex_constraints(replace(
        sample, containing_main_axis_size=AvailableSize(400, True),
    ))
    assert (result.basis, result.min_size, result.max_size) == (80, 80, 280)


def test_definite_zero_percentage_not_auto(sample):
    result = resolve_percentage_flex_constraints(replace(
        sample, basis=Length.percent(0), minimum=Length.px(0),
        maximum=Length(LengthKind.NONE),
    ))
    assert result.basis == 0
    assert result.min_size == 0
    assert result.max_size is None


def test_indefinite_percent_minimum_needs_dependency_phase(sample):
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_constraints(replace(
            sample, containing_main_axis_size=AvailableSize(400, False),
        ))


def test_indefinite_percent_maximum_needs_dependency_phase(sample):
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_constraints(replace(
            sample, minimum=Length.px(0),
            containing_main_axis_size=AvailableSize(None, False),
        ))


def test_explicit_none_maximum_is_unbounded(sample):
    result = resolve_percentage_flex_constraints(replace(
        sample, maximum=Length(LengthKind.NONE),
    ))
    assert result.max_size is None


def test_indefinite_percent_basis_requires_intrinsic_snapshot(sample):
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_constraints(replace(
            sample, flex_container_main_size=AvailableSize(None, False),
        ))


def test_indefinite_basis_uses_snapshot_but_not_indefinite_min_max(sample):
    measurement = IntrinsicFlexInput(
        intrinsic=IntrinsicSizes(
            min_content_width=30, max_content_width=120,
            min_content_height=10, max_content_height=70,
            preferred_width=100, preferred_height=60,
        ),
        axis=MainAxis.HORIZONTAL,
        flex_basis=Length(LengthKind.CONTENT),
    )
    result = resolve_percentage_flex_constraints(replace(
        sample, basis=Length.percent(0), minimum=Length.px(0),
        maximum=Length(LengthKind.NONE),
        flex_container_main_size=AvailableSize(None, False),
        intrinsic=measurement,
    ))
    assert result.basis == 100  # 120px content minus 20px border/padding


def test_unresolved_auto_minimum_is_not_assumed_zero(sample):
    with pytest.raises(SFLECapabilityError):
        resolve_percentage_flex_constraints(replace(
            sample, minimum=Length(LengthKind.AUTO),
        ))


def test_invalid_contracts_rejected(sample):
    with pytest.raises(TypeError):
        replace(sample, horizontal="false")
    with pytest.raises(ValueError):
        resolve_percentage_flex_constraints(replace(sample, padding_border=-1))
