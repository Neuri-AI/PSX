"""Kivy high-DPI diagnostics: distinguish window points and drawable pixels.

This module deliberately does *not* mutate Metrics.density or apply a second
geometry transform. Cocoa/SDL2 may already expose drawable-space coordinates
to Kivy widgets; a second transform would corrupt hit testing and readback.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class KivyDisplayScale:
    """Observed drawable pixels per window-coordinate unit, per axis."""

    drawable_width: float
    drawable_height: float
    window_width: float
    window_height: float

    def __post_init__(self) -> None:
        for value in (
            self.drawable_width, self.drawable_height,
            self.window_width, self.window_height,
        ):
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise TypeError("Kivy display dimensions must be numeric.")
            if not isfinite(value) or value <= 0:
                raise ValueError("Kivy display dimensions must be finite and positive.")

    @classmethod
    def from_window(cls, window: object) -> "KivyDisplayScale":
        """Read both public Kivy size spaces without changing window state."""
        drawable = window.size
        system = window.system_size
        return cls(
            float(drawable[0]), float(drawable[1]),
            float(system[0]), float(system[1]),
        )

    @property
    def x(self) -> float:
        return self.drawable_width / self.window_width

    @property
    def y(self) -> float:
        return self.drawable_height / self.window_height

    @property
    def uniform(self) -> float:
        """Require uniform pixel density; no silent anisotropic CSS stretching."""
        if abs(self.x - self.y) > 0.02:
            raise ValueError(
                "Kivy drawable/system dimensions have unequal axis scales."
            )
        return (self.x + self.y) / 2

    def snapshot(self) -> dict[str, float]:
        """Comparable, serializable observation for Retina acceptance receipts."""
        return {
            "drawable_width": self.drawable_width,
            "drawable_height": self.drawable_height,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "scale_x": self.x,
            "scale_y": self.y,
        }
