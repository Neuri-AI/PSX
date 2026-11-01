"""F2.2.1: pure intrinsic flex-basis and automatic minimum-size resolution.

Accepts immutable intrinsic snapshots collected by UI-thread adapters. This
module never measures fonts/widgets. Aspect-ratio transfer requires an
explicit immutable cross-size suggestion; it never invents one.
"""

from __future__ import annotations

from psx.layout.contracts.recursive_tree import MainAxis, OverflowMode, IntrinsicFlexInput

from dataclasses import dataclass
from enum import Enum

from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError
from psx.layout.fallback.flex_math import FlexBasis, _number
from psx.layout.contracts.lengths import Length, LengthKind
from psx.layout.contracts.model import IntrinsicSizes


def _metrics(request: IntrinsicFlexInput) -> tuple[float, float, float]:
    metric = request.intrinsic
    if request.axis == MainAxis.HORIZONTAL:
        return metric.min_content_width, metric.max_content_width, metric.preferred_width
    return metric.min_content_height, metric.max_content_height, metric.preferred_height


def _unsupported(message: str) -> None:
    raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, message)


def _transferred_main_suggestion(request: IntrinsicFlexInput) -> float | None:
    if request.aspect_ratio is None:
        return None
    cross = request.preferred_cross_size
    if cross is None:
        cross = (request.intrinsic.preferred_height
                 if request.axis == MainAxis.HORIZONTAL
                 else request.intrinsic.preferred_width)
    if request.axis == MainAxis.HORIZONTAL:
        return cross * request.aspect_ratio
    return cross / request.aspect_ratio


def resolve_intrinsic_flex_basis(request: IntrinsicFlexInput) -> float:
    """Resolve a constrained set of content-based flex-basis values.

    `auto` uses a *definite* main-size suggestion if provided, otherwise
    content-based max-content. A typed aspect ratio with a definite measured
    or resolved cross-size suggestion transfers into the main axis.
    """

    if (request.has_aspect_ratio_transfer and
            (request.aspect_ratio is None or request.preferred_cross_size is None)):
        _unsupported("Aspect-ratio transfer requires a typed ratio and explicit cross-size measurement.")
    minimum, maximum, _ = _metrics(request)
    basis = request.flex_basis
    transferred = _transferred_main_suggestion(request)
    if basis.kind == LengthKind.PX:
        assert basis.value is not None
        if basis.value < 0:
            raise ValueError("flex-basis cannot be negative.")
        return basis.value
    if basis.kind == LengthKind.MIN_CONTENT:
        return minimum
    if basis.kind in (LengthKind.MAX_CONTENT, LengthKind.CONTENT):
        return maximum
    if basis.kind == LengthKind.AUTO:
        if request.preferred_main_size is not None:
            return request.preferred_main_size
        return transferred if transferred is not None else maximum
    _unsupported(f"Intrinsic flex-basis {basis.kind.value!r} is not supported by this slice.")


def resolve_automatic_main_minimum(request: IntrinsicFlexInput) -> float:
    """Resolve CSS Flexbox §4.5 automatic minimum for a limited item class.

    Non-scroll containers use content-size suggestion capped by the definite
    specified-size suggestion and definite max main size. Scroll containers
    have zero automatic minimum. Replaced elements use the smaller
    content/transferred suggestion; other elements use the larger value.
    Explicit min-width/height overrides the automatic minimum.
    """

    if request.min_main_size is not None:
        return request.min_main_size
    if request.scroll_container:
        return 0.0
    min_content, _, _ = _metrics(request)
    suggested = min_content
    transferred = _transferred_main_suggestion(request)
    if transferred is not None:
        suggested = min(suggested, transferred) if request.replaced else max(suggested, transferred)
    if request.preferred_main_size is not None:
        suggested = min(suggested, request.preferred_main_size)
    if request.max_main_size is not None:
        suggested = min(suggested, request.max_main_size)
    return suggested


def build_intrinsic_flex_basis(request: IntrinsicFlexInput) -> FlexBasis:
    """Feed resolved intrinsic content sizes into the existing flex math kernel."""

    basis = resolve_intrinsic_flex_basis(request)
    minimum = resolve_automatic_main_minimum(request)
    maximum = request.max_main_size
    if maximum is not None:
        minimum = min(minimum, maximum)
    hypothetical = max(minimum, basis)
    if maximum is not None:
        hypothetical = min(hypothetical, maximum)
    return FlexBasis(
        basis=basis,
        hypothetical=hypothetical,
        grow=request.grow,
        shrink=request.shrink,
        min_size=minimum,
        max_size=maximum,
    )
