"""Signed, saturating Blink-style LayoutUnit at 1/64 CSS pixel.

Source: Chromium 153.0.8010.12
third_party/blink/renderer/platform/geometry/layout_unit.h
FixedPoint<6,int32_t>, ClampRawValue, FromDoubleRound/FromFloatFloor,
FixedPoint(double), MulDiv. Nonfinite inputs are rejected by SFLE.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

SCALE = 64
I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1


def _saturate(value: int) -> int:
    return max(I32_MIN, min(I32_MAX, value))


def _scaled(value: float, mode: str) -> int:
    if not math.isfinite(value):
        raise ValueError("LayoutUnit rejects NaN and infinity.")
    scaled = value * SCALE
    if scaled >= I32_MAX + 1:
        return I32_MAX
    if scaled <= I32_MIN - 1:
        return I32_MIN
    if mode == "trunc":
        raw = math.trunc(scaled)
    elif mode == "floor":
        raw = math.floor(scaled)
    elif mode == "ceil":
        raw = math.ceil(scaled)
    elif mode == "nearest":
        raw = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
    else:
        raise ValueError(f"Unknown LayoutUnit conversion mode: {mode}.")
    return _saturate(raw)


def nearest_layout_px(value: float) -> float:
    """Round directly to Blink's 1/64px grid without a temporary LayoutUnit.

    Exactly the same signed half-away-from-zero rounding, finite checks and
    i32 saturation as LayoutUnit.from_nearest(value).to_px(). Intended for
    hot native Block/Inline rectangle construction.
    """
    return _scaled(value, "nearest") / SCALE


@dataclass(frozen=True, slots=True)
class LayoutUnit:
    raw: int

    def __post_init__(self) -> None:
        if isinstance(self.raw, bool) or not isinstance(self.raw, int):
            raise TypeError("LayoutUnit raw storage must be an integer.")
        object.__setattr__(self, "raw", _saturate(self.raw))

    @classmethod
    def from_raw(cls, raw: int) -> "LayoutUnit":
        return cls(raw)

    @classmethod
    def from_trunc(cls, value: float) -> "LayoutUnit":
        return cls(_scaled(value, "trunc"))

    @classmethod
    def from_floor(cls, value: float) -> "LayoutUnit":
        return cls(_scaled(value, "floor"))

    @classmethod
    def from_ceil(cls, value: float) -> "LayoutUnit":
        return cls(_scaled(value, "ceil"))

    @classmethod
    def from_nearest(cls, value: float) -> "LayoutUnit":
        return cls(_scaled(value, "nearest"))

    def to_px(self) -> float:
        return self.raw / SCALE

    def __add__(self, other: "LayoutUnit") -> "LayoutUnit":
        if not isinstance(other, LayoutUnit):
            return NotImplemented
        return LayoutUnit(self.raw + other.raw)

    def __sub__(self, other: "LayoutUnit") -> "LayoutUnit":
        if not isinstance(other, LayoutUnit):
            return NotImplemented
        return LayoutUnit(self.raw - other.raw)

    def mul_div(self, multiplier: "LayoutUnit", divisor: "LayoutUnit") -> "LayoutUnit":
        """Fused (self.raw * multiplier.raw)/divisor.raw, trunc toward 0."""
        if divisor.raw == 0:
            raise ZeroDivisionError("LayoutUnit MulDiv divisor cannot be zero.")
        num = self.raw * multiplier.raw
        q = abs(num) // abs(divisor.raw)
        if (num < 0) != (divisor.raw < 0):
            q = -q
        return LayoutUnit(_saturate(q))
