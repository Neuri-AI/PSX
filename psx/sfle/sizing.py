"""Property-aware CSS length resolution, without inventing definite sizes.

This F2.2 slice separates resolution of definite percentages from unresolved
CSS values. It does not implement intrinsic measurement, cyclic percentages,
flex-basis:auto, or CSS automatic minimum-size computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import DiagnosticCode, SFLECapabilityError
from .lengths import Length, LengthKind
from .model import AvailableSize


class SizeProperty(str, Enum):
    WIDTH = "width"
    HEIGHT = "height"
    FLEX_BASIS = "flex_basis"
    MIN_WIDTH = "min_width"
    MIN_HEIGHT = "min_height"
    MAX_WIDTH = "max_width"
    MAX_HEIGHT = "max_height"
    MARGIN = "margin"
    PADDING = "padding"
    GAP = "gap"
    BORDER = "border"


class ResolutionKind(str, Enum):
    USED = "used"
    AUTO = "auto"
    INTRINSIC = "intrinsic"
    UNRESOLVED_PERCENT = "unresolved_percent"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ResolvedLength:
    """A resolved used number or a semantically retained unresolved keyword."""

    kind: ResolutionKind
    value: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResolutionKind):
            raise TypeError("kind must be ResolutionKind.")
        if self.kind == ResolutionKind.USED:
            if self.value is None:
                raise ValueError("Used lengths require a numeric value.")
            from .flex_math import _number

            object.__setattr__(self, "value", _number(self.value, "used length"))
        elif self.value is not None:
            raise ValueError("Unresolved lengths must not contain a number.")

    def require_used(self) -> float:
        """Require a numeric size at a boundary that cannot accept deferral."""
        if self.kind != ResolutionKind.USED:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"CSS size is {self.kind.value}; numeric resolution is required.",
            )
        assert self.value is not None
        return self.value


_INTRINSIC = frozenset({
    LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT,
    LengthKind.FIT_CONTENT, LengthKind.CONTENT,
})
_ALLOW_AUTO = frozenset({
    SizeProperty.WIDTH, SizeProperty.HEIGHT, SizeProperty.FLEX_BASIS,
    SizeProperty.MIN_WIDTH, SizeProperty.MIN_HEIGHT, SizeProperty.MARGIN,
})
_ALLOW_NONE = frozenset({SizeProperty.MAX_WIDTH, SizeProperty.MAX_HEIGHT})
_PERCENT = frozenset({
    SizeProperty.WIDTH, SizeProperty.HEIGHT, SizeProperty.FLEX_BASIS,
    SizeProperty.MIN_WIDTH, SizeProperty.MIN_HEIGHT, SizeProperty.MAX_WIDTH,
    SizeProperty.MAX_HEIGHT, SizeProperty.MARGIN, SizeProperty.PADDING,
    SizeProperty.GAP,
})
_INTRINSIC_PROPS = frozenset({
    SizeProperty.WIDTH, SizeProperty.HEIGHT, SizeProperty.FLEX_BASIS,
    SizeProperty.MIN_WIDTH, SizeProperty.MIN_HEIGHT,
    SizeProperty.MAX_WIDTH, SizeProperty.MAX_HEIGHT,
})


def resolve_length(
    length: Length,
    property_name: SizeProperty,
    *,
    containing_inline_size: AvailableSize,
    containing_block_axis_size: AvailableSize,
    flex_container_main_size: AvailableSize,
) -> ResolvedLength:
    """Resolve a value when its CSS reference size is known and definite.

    Percentage padding and physical margins use the containing block's
    *inline* size, including top/bottom edges in horizontal writing mode.
    Percentage flex-basis uses the definite flex container MAIN size.
    Width/height/min/max resolve against the relevant containing-block
    axis. Percent gap cyclic/intrinsic rules are not yet implemented, so
    percentages for gap are rejected rather than incorrectly resolved.
    """

    if not isinstance(length, Length) or not isinstance(property_name, SizeProperty):
        raise TypeError("Expected Length and SizeProperty.")
    if not all(isinstance(v, AvailableSize) for v in (
        containing_inline_size, containing_block_axis_size, flex_container_main_size
    )):
        raise TypeError("All reference dimensions must be AvailableSize.")

    kind = length.kind
    if kind == LengthKind.PX:
        value = length.value
        assert value is not None
        if value < 0 and property_name != SizeProperty.MARGIN:
            raise ValueError(f"Negative {property_name.value} is invalid.")
        return ResolvedLength(ResolutionKind.USED, value)

    if kind == LengthKind.PERCENT:
        if property_name not in _PERCENT:
            raise SFLECapabilityError(
                DiagnosticCode.INVALID_LENGTH, f"Percent is invalid for {property_name.value}."
            )
        assert length.value is not None
        if length.value < 0 and property_name != SizeProperty.MARGIN:
            raise ValueError(f"Negative {property_name.value} percentage is invalid.")
        if property_name == SizeProperty.GAP:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Percentage gap cyclic/intrinsic semantics are not implemented.",
            )
        ref = (
            containing_inline_size if property_name in (
                SizeProperty.MARGIN, SizeProperty.PADDING,
            )
            else flex_container_main_size if property_name == SizeProperty.FLEX_BASIS
            else containing_block_axis_size
        )
        if not ref.definite:
            return ResolvedLength(ResolutionKind.UNRESOLVED_PERCENT)
        assert ref.value is not None
        return ResolvedLength(ResolutionKind.USED, ref.value * length.value)

    if kind == LengthKind.AUTO and property_name in _ALLOW_AUTO:
        return ResolvedLength(ResolutionKind.AUTO)
    if kind == LengthKind.NONE and property_name in _ALLOW_NONE:
        return ResolvedLength(ResolutionKind.NONE)
    if kind in _INTRINSIC and property_name in _INTRINSIC_PROPS:
        return ResolvedLength(ResolutionKind.INTRINSIC)
    raise SFLECapabilityError(
        DiagnosticCode.INVALID_LENGTH,
        f"Unsupported {kind.value} value for {property_name.value}.",
    )
