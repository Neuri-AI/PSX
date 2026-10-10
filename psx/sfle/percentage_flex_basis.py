"""F2.2.2: context-aware percentage flex-basis with intrinsic fallback.

Percentage flex-basis uses the flex container's *definite main size*.
When that size is indefinite, CSS computes the used flex basis from content.
This restricted helper requires a premeasured non-replaced intrinsic snapshot;
it does not perform cyclic measurement, aspect-ratio transfer or auto min size.
"""

from __future__ import annotations

from dataclasses import replace

from .errors import DiagnosticCode, SFLECapabilityError
from .intrinsic import IntrinsicFlexInput, resolve_intrinsic_flex_basis
from .lengths import Length, LengthKind
from .model import AvailableSize


def resolve_percentage_flex_basis(
    basis: Length,
    flex_main_size: AvailableSize,
    content: IntrinsicFlexInput,
) -> float:
    """Resolve definite percent, or fall back to measured max-content.

    A percentage with an indefinite main-size reference takes the
    content-based fallback. The supplied content must be an existing
    measurement of the same item and axis, not a guessed hint.
    """
    if not isinstance(basis, Length) or not isinstance(flex_main_size, AvailableSize):
        raise TypeError("Expected Length and AvailableSize.")
    if not isinstance(content, IntrinsicFlexInput):
        raise TypeError("content must be IntrinsicFlexInput.")
    if basis.kind != LengthKind.PERCENT:
        raise SFLECapabilityError(
            DiagnosticCode.INVALID_LENGTH, "Expected percentage flex-basis."
        )
    assert basis.value is not None
    if basis.value < 0:
        raise ValueError("flex-basis percentage cannot be negative.")
    if flex_main_size.definite:
        assert flex_main_size.value is not None
        return basis.value * flex_main_size.value
    return resolve_intrinsic_flex_basis(
        replace(
            content, flex_basis=Length(LengthKind.CONTENT)
        )
    )
