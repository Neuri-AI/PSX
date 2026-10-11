"""F2.2.2 typed length-to-FlexBasis boundary for definite used constraints.

This is not the complete CSS measurement algorithm. It connects property-
aware percent lengths, the measured content fallback for indefinite percent
flex-basis, and border/content-box min/max normalization. Indefinite percent
min/max is *deferred* with an explicit capability error instead of guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLECapabilityError
from .flex_math import FlexBasis
from .intrinsic import (
    IntrinsicFlexInput, resolve_automatic_main_minimum,
    resolve_intrinsic_flex_basis,
)
from .lengths import Length, LengthKind
from .model import AvailableSize
from .percentage_box_sizing import BoxSizing, normalize_flex_box_basis
from .percentage_flex_basis import resolve_percentage_flex_basis
from .sizing import ResolutionKind, SizeProperty, resolve_length


@dataclass(frozen=True, slots=True)
class PercentageFlexConstraints:
    basis: Length
    minimum: Length
    maximum: Length
    containing_inline_size: AvailableSize
    containing_main_axis_size: AvailableSize
    flex_container_main_size: AvailableSize
    padding_border: float
    sizing: BoxSizing
    grow: float = 0.0
    shrink: float = 1.0
    intrinsic: IntrinsicFlexInput | None = None
    horizontal: bool = True

    def __post_init__(self) -> None:
        if not all(isinstance(value, Length) for value in (
            self.basis, self.minimum, self.maximum
        )):
            raise TypeError("basis/minimum/maximum require typed Length values.")
        if not all(isinstance(value, AvailableSize) for value in (
            self.containing_inline_size, self.containing_main_axis_size,
            self.flex_container_main_size,
        )):
            raise TypeError("reference sizes must be AvailableSize.")
        if not isinstance(self.sizing, BoxSizing):
            raise TypeError("sizing must be BoxSizing.")
        if self.intrinsic is not None and not isinstance(self.intrinsic, IntrinsicFlexInput):
            raise TypeError("intrinsic must be IntrinsicFlexInput or None.")
        if type(self.horizontal) is not bool:
            raise TypeError("horizontal must be bool.")


def _needs_used(label: str, kind: ResolutionKind) -> None:
    raise SFLECapabilityError(
        DiagnosticCode.UNSUPPORTED_FEATURE,
        f"{label} remains {kind.value}; a measurement/dependency phase is required.",
    )


def resolve_percentage_flex_constraints(
    request: PercentageFlexConstraints,
) -> FlexBasis:
    """Produce a validated content-box FlexBasis only with sufficient inputs.

    min:auto and explicit intrinsic min/max cannot be inferred at this
    boundary. Callers must provide a separately resolved minimum from the
    intrinsic/scroll-container stage. max:none is supported as unbounded.
    """
    if not isinstance(request, PercentageFlexConstraints):
        raise TypeError("request must be PercentageFlexConstraints.")

    def resolve(value: Length, property_name: SizeProperty):
        return resolve_length(
            value, property_name,
            containing_inline_size=request.containing_inline_size,
            containing_block_axis_size=request.containing_main_axis_size,
            flex_container_main_size=request.flex_container_main_size,
        )

    min_prop = SizeProperty.MIN_WIDTH if request.horizontal else SizeProperty.MIN_HEIGHT
    max_prop = SizeProperty.MAX_WIDTH if request.horizontal else SizeProperty.MAX_HEIGHT
    minimum = resolve(request.minimum, min_prop)
    maximum = resolve(request.maximum, max_prop)

    if minimum.kind == ResolutionKind.USED:
        assert minimum.value is not None
        minimum_value = minimum.value
    elif minimum.kind in (
        ResolutionKind.AUTO, ResolutionKind.INTRINSIC,
        ResolutionKind.UNRESOLVED_PERCENT,
    ) and request.intrinsic is not None:
        minimum_value = resolve_automatic_main_minimum(request.intrinsic)
    else:
        _needs_used("Minimum main size", minimum.kind)

    if maximum.kind == ResolutionKind.USED:
        maximum_value = maximum.value
    elif maximum.kind in (ResolutionKind.NONE, ResolutionKind.UNRESOLVED_PERCENT):
        maximum_value = None
    elif maximum.kind == ResolutionKind.INTRINSIC and request.intrinsic is not None:
        metric = request.intrinsic.intrinsic
        if request.horizontal:
            maximum_value = (metric.min_content_width if request.maximum.kind == LengthKind.MIN_CONTENT
                             else metric.max_content_width)
        else:
            maximum_value = (metric.min_content_height if request.maximum.kind == LengthKind.MIN_CONTENT
                             else metric.max_content_height)
    else:
        _needs_used("Maximum main size", maximum.kind)

    basis = resolve(request.basis, SizeProperty.FLEX_BASIS)
    if basis.kind == ResolutionKind.USED:
        assert basis.value is not None
        basis_value = basis.value
    elif (
        request.basis.kind == LengthKind.PERCENT
        and basis.kind == ResolutionKind.UNRESOLVED_PERCENT
        and request.intrinsic is not None
    ):
        basis_value = resolve_percentage_flex_basis(
            request.basis, request.flex_container_main_size, request.intrinsic,
        )
    elif basis.kind in (ResolutionKind.AUTO, ResolutionKind.INTRINSIC) and request.intrinsic is not None:
        from dataclasses import replace
        basis_value = resolve_intrinsic_flex_basis(
            replace(request.intrinsic, flex_basis=request.basis)
        )
    else:
        _needs_used("Flex basis", basis.kind)

    return normalize_flex_box_basis(
        basis_value, request.padding_border, request.sizing,
        min_size=minimum_value, max_size=maximum_value,
        grow=request.grow, shrink=request.shrink,
    )
