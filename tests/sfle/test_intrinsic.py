"""F2.2.1 intrinsic flex-basis/automatic minimum-size semantic tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.errors import DiagnosticCode, SFLECapabilityError
from psx.sfle.intrinsic import (
    IntrinsicFlexInput, MainAxis, OverflowMode, build_intrinsic_flex_basis,
    resolve_automatic_main_minimum, resolve_intrinsic_flex_basis,
)
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import IntrinsicSizes


@pytest.fixture
def request() -> IntrinsicFlexInput:
    return IntrinsicFlexInput(
        intrinsic=IntrinsicSizes(
            min_content_width=40, max_content_width=130,
            min_content_height=20, max_content_height=70,
            preferred_width=90, preferred_height=40,
        ),
        axis=MainAxis.HORIZONTAL,
        flex_basis=Length(LengthKind.AUTO),
        grow=1,
    )


def test_auto_flex_basis_uses_max_content_when_main_size_not_specified(request):
    assert resolve_intrinsic_flex_basis(request) == 130
    flex = build_intrinsic_flex_basis(request)
    assert (flex.basis, flex.min_size, flex.hypothetical) == (130, 40, 130)


def test_content_and_explicit_intrinsic_keywords(request):
    assert resolve_intrinsic_flex_basis(
        replace(request, flex_basis=Length(LengthKind.CONTENT))
    ) == 130
    assert resolve_intrinsic_flex_basis(
        replace(request, flex_basis=Length(LengthKind.MIN_CONTENT))
    ) == 40
    assert resolve_intrinsic_flex_basis(
        replace(request, flex_basis=Length(LengthKind.MAX_CONTENT))
    ) == 130


def test_auto_min_is_capped_by_definite_specified_suggestion(request):
    candidate = replace(request, preferred_main_size=25)
    assert resolve_automatic_main_minimum(candidate) == 25
    assert resolve_intrinsic_flex_basis(candidate) == 25


def test_definite_max_clamps_auto_min_and_hypothetical_size(request):
    candidate = replace(request, max_main_size=30)
    assert resolve_automatic_main_minimum(candidate) == 30
    flex = build_intrinsic_flex_basis(candidate)
    assert flex.min_size == 30
    assert flex.hypothetical == 30
    assert flex.basis == 130


def test_explicit_min_overrides_auto_minimum(request):
    candidate = replace(request, min_main_size=0)
    assert resolve_automatic_main_minimum(candidate) == 0
    assert build_intrinsic_flex_basis(candidate).min_size == 0


def test_scroll_container_has_zero_auto_minimum(request):
    candidate = replace(request, overflow=OverflowMode.SCROLL, scroll_container=True)
    assert resolve_automatic_main_minimum(candidate) == 0


def test_overflow_auto_without_actual_scroll_container_keeps_content_min(request):
    candidate = replace(request, overflow=OverflowMode.AUTO, scroll_container=False)
    assert resolve_automatic_main_minimum(candidate) == 40


def test_column_axis_reads_vertical_intrinsic_measurements(request):
    candidate = replace(request, axis=MainAxis.VERTICAL)
    assert resolve_intrinsic_flex_basis(candidate) == 70
    assert resolve_automatic_main_minimum(candidate) == 20


def test_percentage_basis_requires_definite_reference_stage(request):
    candidate = replace(request, flex_basis=Length.percent(0.5))
    with pytest.raises(SFLECapabilityError) as error:
        resolve_intrinsic_flex_basis(candidate)
    assert error.value.code == DiagnosticCode.UNSUPPORTED_FEATURE


def test_aspect_ratio_transfer_is_not_silently_approximated(request):
    candidate = replace(request, has_aspect_ratio_transfer=True)
    with pytest.raises(SFLECapabilityError):
        build_intrinsic_flex_basis(candidate)


def test_scroll_flag_validation(request):
    with pytest.raises(ValueError):
        replace(request, scroll_container=True)
    with pytest.raises(ValueError):
        replace(request, overflow=OverflowMode.SCROLL)


def test_invalid_intrinsic_data_rejected(request):
    with pytest.raises(ValueError):
        replace(request, min_main_size=-1)
    with pytest.raises(ValueError):
        replace(request, min_main_size=50, max_main_size=40)
