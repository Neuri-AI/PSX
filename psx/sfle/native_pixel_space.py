"""Native SFLE device-scale projection and native geometry readback.

SFLE boxes are CSS *logical* px (i32 LayoutUnit, 1/64px). The immediate
native widget APIs use their own coordinate spaces:

* Qt QWidget.setGeometry/geometry use device-independent logical px. Qt
  multiplies those coordinates by devicePixelRatioF when rasterizing. DO
  NOT multiply the coordinates passed to QWidget.setGeometry by DPR.
* Kivy Widget.pos/size use window pixel coordinates already; density
  scales dp/sp *style units*, not these widget coordinates.
* Tk place x/y/width/height are Tk window pixel coordinates; 'tk scaling'
  changes the point/font conversion, not place coordinate semantics.

The device-pixel projection here is for diagnostics, comparison and
future framebuffer-backed adapters, NOT a second layout algorithm or an
instruction to multiply an existing native widget's geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .errors import DiagnosticCode, SFLEError
from .model import Rect


def _pixel_edge(value: float) -> int:
    # Matches the signed LayoutUnit rounding policy for an edge.
    if not math.isfinite(value):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Non-finite device pixel coordinate.")
    return math.floor(value + 0.5)


@dataclass(frozen=True, slots=True)
class DevicePixelSpace:
    """Physical pixels per native widget-API coordinate unit."""

    scale: float
    backend: str

    def __post_init__(self) -> None:
        if self.backend not in {"qt", "kivy", "tk"}:
            raise ValueError("Unsupported SFLE native pixel backend.")
        if isinstance(self.scale, bool) or not isinstance(self.scale, (float, int)):
            raise TypeError("Device scale must be a finite, positive number.")
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("Device scale must be finite and positive.")

    @classmethod
    def from_widget(cls, backend: str, widget: object) -> "DevicePixelSpace":
        if backend == "qt":
            # Both Qt 5 and Qt 6 report QWidget geometry in DIPs. Query
            # the *mounted root* each transaction (not a cached display DPI).
            getter = getattr(widget, "devicePixelRatioF", None)
            if callable(getter):
                return cls(float(getter()), backend)
            legacy = getattr(widget, "devicePixelRatio", None)
            if callable(legacy):
                return cls(float(legacy()), backend)
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Qt SFLE widget does not expose a device pixel ratio.",
            )
        if backend not in {"kivy", "tk"}:
            raise ValueError("Unsupported SFLE native pixel backend.")
        # Kivy density and Tk scaling factor are used by style/text metrics,
        # not to multiply positions already expressed in toolkit pixels.
        return cls(1.0, backend)

    def to_physical(self, rect: Rect) -> Rect:
        """Quantize each *edge* (not width independently) to physical pixels.

        Edge rounding prevents adjacent fractional boundaries producing
        an unaccounted pixel gap at non-integer DPR.
        """
        x0 = _pixel_edge(rect.x * self.scale)
        y0 = _pixel_edge(rect.y * self.scale)
        x1 = _pixel_edge((rect.x + rect.width) * self.scale)
        y1 = _pixel_edge((rect.y + rect.height) * self.scale)
        return Rect(x0, y0, x1 - x0, y1 - y0)

    def error(self, expected: Rect, native_actual: Rect) -> tuple[float, float]:
        """Return (native logical error, device physical error)."""
        axes = ("x", "y", "width", "height")
        logical = max(
            abs(getattr(expected, axis) - getattr(native_actual, axis))
            for axis in axes
        )
        projected = self.to_physical(expected)
        observed = self.to_physical(native_actual)
        physical = max(
            abs(getattr(projected, axis) - getattr(observed, axis))
            for axis in axes
        )
        return logical, physical

    @property
    def allowed_physical_error(self) -> int:
        # One *native coordinate-unit* readback tolerance translates to
        # ceil(DPR) physical pixels for Qt's integer QWidget geometry API.
        return max(1, math.ceil(self.scale))
