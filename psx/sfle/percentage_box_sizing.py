"""F2.2.2: explicit percentage-gap cycles and used CSS box sizing.

This module resolves only a known definite percentage gap or the CSS cyclic
intrinsic-contribution case (zero contribution). An indefinite used gap stays
unresolved; callers must not treat the intrinsic zero as its final used value.

Width/height normalization converts a *definite specified* content-box or
border-box size into nonnegative used content and border sizes. Borders/padding
must already be resolved in logical pixels. Definite min/max constraints and flex-basis can also be normalized to
content-box units for the pure flex solver; intrinsic/auto resolution is elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import DiagnosticCode, SFLECapabilityError
from .flex_math import _number
from .lengths import Length, LengthKind
from .model import AvailableSize


class BoxSizing(str, Enum):
    CONTENT_BOX = "content-box"
    BORDER_BOX = "border-box"


class GapPhase(str, Enum):
    INTRINSIC_CONTRIBUTION = "intrinsic_contribution"
    USED_LAYOUT = "used_layout"


@dataclass(frozen=True, slots=True)
class UsedBoxSize:
    content: float
    border_box: float
    padding_border: float


def resolve_percentage_gap(
    length: Length, reference: AvailableSize, *, phase: GapPhase
) -> float:
    """Resolve a gap along its corresponding container axis.

    For an indefinite percentage gap, the cyclic percentage contributes zero
    to intrinsic sizing only. The *used-layout* value cannot be inferred and
    is rejected until the container's definite used size is available.
    """

    if not isinstance(length, Length) or not isinstance(reference, AvailableSize):
        raise TypeError("Expected Length and AvailableSize.")
    if not isinstance(phase, GapPhase):
        raise TypeError("phase must be a GapPhase.")
    if length.kind == LengthKind.PX:
        assert length.value is not None
        if length.value < 0:
            raise ValueError("gap must not be negative.")
        return length.value
    if length.kind != LengthKind.PERCENT:
        raise SFLECapabilityError(
            DiagnosticCode.INVALID_LENGTH, f"Unsupported gap length: {length.kind.value}"
        )
    assert length.value is not None
    if length.value < 0:
        raise ValueError("gap percentage must not be negative.")
    if reference.definite:
        assert reference.value is not None
        return length.value * reference.value
    if phase == GapPhase.INTRINSIC_CONTRIBUTION:
        return 0.0
    raise SFLECapabilityError(
        DiagnosticCode.UNSUPPORTED_FEATURE,
        "Indefinite percentage gap cannot be resolved for used layout.",
    )


def normalize_box_size(
    specified: float, padding_border: float, sizing: BoxSizing
) -> UsedBoxSize:
    """Apply CSS box-sizing to an already-definite specified width/height.

    Under border-box, border/padding are a floor on the used border size:
    a specified border-box narrower than its fixed edges leaves zero content.
    """

    if not isinstance(sizing, BoxSizing):
        raise TypeError("sizing must be BoxSizing.")
    value = _number(specified, "specified")
    edges = _number(padding_border, "padding_border")
    if value < 0 or edges < 0:
        raise ValueError("specified size and padding/border must be nonnegative.")
    content = value if sizing == BoxSizing.CONTENT_BOX else max(0.0, value - edges)
    return UsedBoxSize(content=content, border_box=content + edges, padding_border=edges)


def normalize_flex_box_basis(
    basis: float,
    padding_border: float,
    sizing: BoxSizing,
    *,
    min_size: float = 0.0,
    max_size: float | None = None,
    grow: float = 0.0,
    shrink: float = 1.0,
) -> "FlexBasis":
    """Normalize definite CSS flex-basis and min/max to content-box units.

    CSS box-sizing determines which box a definite flex basis and definite
    min/max main-size constraints describe. The padding/border floor is
    subtracted from border-box constraints; if max < min, min wins per CSS.
    No percentages, auto minima or intrinsically determined bounds are
    implicitly resolved by this helper.
    """

    from .flex_math import FlexBasis

    used_basis = normalize_box_size(basis, padding_border, sizing).content
    used_minimum = normalize_box_size(min_size, padding_border, sizing).content
    used_maximum = (
        normalize_box_size(max_size, padding_border, sizing).content
        if max_size is not None else None
    )
    if used_maximum is not None and used_maximum < used_minimum:
        used_maximum = used_minimum
    hypothetical = max(used_basis, used_minimum)
    if used_maximum is not None:
        hypothetical = min(hypothetical, used_maximum)
    return FlexBasis(
        basis=used_basis, hypothetical=hypothetical, min_size=used_minimum,
        max_size=used_maximum, grow=grow, shrink=shrink,
    )
