"""CSS sizing reference dimensions and unsupported semantics must stay explicit."""

from __future__ import annotations

import pytest

from psx.sfle.errors import DiagnosticCode, SFLECapabilityError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize
from psx.sfle.sizing import ResolutionKind, SizeProperty, resolve_length


def definite(value: float) -> AvailableSize:
    return AvailableSize(value, True)


def indefinite() -> AvailableSize:
    return AvailableSize(None, False)


def resolve(
    length: Length,
    property_name: SizeProperty,
    *,
    inline: AvailableSize = definite(200),
    axis: AvailableSize = definite(700),
    main: AvailableSize = definite(300),
):
    return resolve_length(
        length, property_name,
        containing_inline_size=inline,
        containing_block_axis_size=axis,
        flex_container_main_size=main,
    )


@pytest.mark.parametrize("property_name", [SizeProperty.MARGIN, SizeProperty.PADDING])
def test_physical_edges_use_containing_inline_reference(property_name):
    result = resolve(Length.percent(0.1), property_name)
    assert result.kind == ResolutionKind.USED
    assert result.value == 20


def test_flex_basis_uses_definite_flex_main_reference():
    assert resolve(Length.percent(0.5), SizeProperty.FLEX_BASIS).value == 150


@pytest.mark.parametrize("property_name", [
    SizeProperty.WIDTH, SizeProperty.HEIGHT, SizeProperty.MIN_WIDTH,
    SizeProperty.MAX_HEIGHT,
])
def test_sizing_percentage_uses_corresponding_containing_axis(property_name):
    assert resolve(Length.percent(0.25), property_name).value == 175


def test_indefinite_percent_does_not_become_zero():
    result = resolve(Length.percent(0.5), SizeProperty.WIDTH, axis=indefinite())
    assert result.kind == ResolutionKind.UNRESOLVED_PERCENT
    assert result.value is None
    with pytest.raises(SFLECapabilityError) as error:
        result.require_used()
    assert error.value.code == DiagnosticCode.UNSUPPORTED_FEATURE


def test_definite_zero_is_distinct_from_indefinite():
    assert resolve(
        Length.percent(0.5), SizeProperty.WIDTH, axis=definite(0)
    ).require_used() == 0


def test_keywords_remain_tagged_not_silently_reinterpreted():
    assert resolve(Length(LengthKind.AUTO), SizeProperty.FLEX_BASIS).kind == ResolutionKind.AUTO
    assert resolve(Length(LengthKind.MIN_CONTENT), SizeProperty.WIDTH).kind == ResolutionKind.INTRINSIC
    assert resolve(Length(LengthKind.NONE), SizeProperty.MAX_WIDTH).kind == ResolutionKind.NONE


def test_negative_margins_are_valid_but_negative_padding_is_not():
    assert resolve(Length.percent(-0.1), SizeProperty.MARGIN).require_used() == -20
    with pytest.raises(ValueError):
        resolve(Length.px(-1), SizeProperty.PADDING)
    with pytest.raises(ValueError):
        resolve(Length.percent(-0.1), SizeProperty.PADDING)


def test_percentage_gap_is_capability_gated():
    with pytest.raises(SFLECapabilityError) as error:
        resolve(Length.percent(0.1), SizeProperty.GAP)
    assert error.value.code == DiagnosticCode.UNSUPPORTED_FEATURE


def test_border_percent_is_invalid_not_unresolved():
    with pytest.raises(SFLECapabilityError) as error:
        resolve(Length.percent(0.1), SizeProperty.BORDER)
    assert error.value.code == DiagnosticCode.INVALID_LENGTH


def test_bad_keyword_for_property_rejected():
    with pytest.raises(SFLECapabilityError):
        resolve(Length(LengthKind.NORMAL), SizeProperty.WIDTH)
