"""Typed, immutable CSS-like lengths for the backend-neutral SFLE core.

A percentage is stored as a *fraction*, not resolved during parsing. The
layout algorithm must select the applicable CSS reference dimension.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from dataclasses import dataclass
from enum import Enum


class LengthKind(str, Enum):
    """Discriminants shared by Python and the future Rust layout core."""

    PX = "px"
    PERCENT = "percent"
    VW = "vw"
    VH = "vh"
    VMIN = "vmin"
    VMAX = "vmax"
    AUTO = "auto"
    MIN_CONTENT = "min-content"
    MAX_CONTENT = "max-content"
    FIT_CONTENT = "fit-content"
    CONTENT = "content"
    NONE = "none"
    NORMAL = "normal"


_NUMERIC_KINDS = frozenset({LengthKind.PX, LengthKind.PERCENT, LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX})
_PERCENT_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))%$")
_PX_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))px$")
_VIEWPORT_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))(vw|vh|vmin|vmax)$")


@dataclass(frozen=True, slots=True)
class Length:
    """Discriminated CSS length; special keywords never carry a payload."""

    kind: LengthKind
    value: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LengthKind):
            raise TypeError("Length.kind must be a LengthKind.")
        if self.kind in _NUMERIC_KINDS:
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise TypeError("Numeric lengths require an int or float payload.")
            if not math.isfinite(self.value):
                raise ValueError("Length payload must be finite.")
            object.__setattr__(self, "value", float(self.value))
        elif self.value is not None:
            raise ValueError(f"{self.kind.value} must not have a numeric payload.")

    @classmethod
    def px(cls, value: int | float) -> Length:
        """Create a logical CSS-pixel length."""

        return cls(LengthKind.PX, value)

    @classmethod
    def percent(cls, fraction: int | float) -> Length:
        """Create a percent using a fraction, e.g. 0.5 for 50%."""

        return cls(LengthKind.PERCENT, fraction)


@lru_cache(maxsize=2048)
def _parse_normalized_length(normalized: str) -> Length | None:
    """Cache only pure, immutable lexical parsing (never viewport resolution)."""
    for kind in LengthKind:
        if normalized == kind.value:
            return Length(kind)

    percent = _PERCENT_RE.fullmatch(normalized)
    if percent:
        return Length.percent(float(percent.group(1)) / 100.0)

    viewport = _VIEWPORT_RE.fullmatch(normalized)
    if viewport:
        return Length(LengthKind(viewport.group(2)), float(viewport.group(1)) / 100.0)

    px = _PX_RE.fullmatch(normalized)
    if px:
        return Length.px(float(px.group(1)))
    return None


def parse_length(value: Length | int | float | str) -> Length:
    """Parse a typed CSS length without resolving its containing dimensions.

    Repeated static CSS literals reuse immutable lexical results. Dynamic
    percentages and viewport units are resolved by the layout caller using
    the current constraints, so a resize never reuses stale geometry.
    """
    if isinstance(value, Length):
        return value
    if isinstance(value, bool):
        raise TypeError("CSS length must not be a bool.")
    if isinstance(value, (int, float)):
        return Length.px(value)
    if not isinstance(value, str):
        raise TypeError("CSS length must be a Length, number or string.")

    result = _parse_normalized_length(value.strip().lower())
    if result is not None:
        return result
    raise ValueError(f"Unsupported CSS length expression: {value!r}.")


_VIEWPORT_KINDS = frozenset({LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX})


def resolve_viewport_length(length: Length, width: float, height: float) -> Length:
    """Resolve a viewport-relative length against logical window content bounds."""
    if length.kind not in _VIEWPORT_KINDS:
        return length
    from math import isfinite
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) or x < 0
           for x in (width, height)):
        raise ValueError("Viewport dimensions must be finite nonnegative values.")
    size = {LengthKind.VW: width, LengthKind.VH: height,
            LengthKind.VMIN: min(width, height),
            LengthKind.VMAX: max(width, height)}[length.kind]
    return Length.px(float(length.value) * size)
