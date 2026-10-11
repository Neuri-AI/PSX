"""F2.2.1: pure intrinsic flex-basis and automatic minimum-size resolution.

Accepts immutable intrinsic snapshots collected by UI-thread adapters. This
module never measures fonts/widgets. Aspect-ratio transfer requires an
explicit immutable cross-size suggestion; it never invents one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import DiagnosticCode, SFLECapabilityError
from .flex_math import FlexBasis, _number
from .lengths import Length, LengthKind
from .model import IntrinsicSizes


class MainAxis(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class OverflowMode(str, Enum):
    VISIBLE = "visible"
    CLIP = "clip"
    HIDDEN = "hidden"
    AUTO = "auto"
    SCROLL = "scroll"


@dataclass(frozen=True, slots=True)
class IntrinsicFlexInput:
    """Premeasured content-box sizes and CSS main-axis sizing decisions.

    width/height are *already definite used content sizes* if provided.
    `scroll_container` is a result from the overflow/scroll-container stage;
    the enum alone cannot determine whether `overflow:auto` scrolls.
    """

    intrinsic: IntrinsicSizes
    axis: MainAxis
    flex_basis: Length
    grow: float = 0.0
    shrink: float = 1.0
    preferred_main_size: float | None = None
    max_main_size: float | None = None
    min_main_size: float | None = None
    overflow: OverflowMode = OverflowMode.VISIBLE
    scroll_container: bool = False
    aspect_ratio: float | None = None
    preferred_cross_size: float | None = None
    replaced: bool = False
    # Compatibility hint; typed ratio and intrinsic cross metrics are authoritative.
    has_aspect_ratio_transfer: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.intrinsic, IntrinsicSizes):
            raise TypeError("intrinsic must be IntrinsicSizes.")
        if not isinstance(self.axis, MainAxis) or not isinstance(self.flex_basis, Length):
            raise TypeError("axis and flex_basis must be typed.")
        if not isinstance(self.overflow, OverflowMode):
            raise TypeError("overflow must be OverflowMode.")
        if (type(self.scroll_container) is not bool or type(self.replaced) is not bool
                or type(self.has_aspect_ratio_transfer) is not bool):
            raise TypeError("scroll, replaced, and aspect-ratio flags must be bool.")
        if self.scroll_container and self.overflow not in (OverflowMode.AUTO, OverflowMode.SCROLL):
            raise ValueError("Scroll container flag requires auto or scroll overflow.")
        if self.overflow == OverflowMode.SCROLL and not self.scroll_container:
            raise ValueError("scroll overflow must be marked as a scroll container.")
        for name in ("grow", "shrink", "preferred_main_size", "max_main_size", "min_main_size"):
            value = getattr(self, name)
            if value is None:
                continue
            numeric = _number(value, name)
            if numeric < 0:
                raise ValueError(f"{name} must be nonnegative.")
            object.__setattr__(self, name, numeric)
        if self.aspect_ratio is not None:
            ratio = _number(self.aspect_ratio, "aspect_ratio")
            if ratio <= 0:
                raise ValueError("aspect_ratio must be positive.")
            object.__setattr__(self, "aspect_ratio", ratio)
        if self.preferred_cross_size is not None:
            cross = _number(self.preferred_cross_size, "preferred_cross_size")
            if cross < 0:
                raise ValueError("preferred_cross_size must be nonnegative.")
            object.__setattr__(self, "preferred_cross_size", cross)
        if self.max_main_size is not None and self.min_main_size is not None:
            if self.max_main_size < self.min_main_size:
                raise ValueError("max_main_size cannot be below min_main_size.")


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
