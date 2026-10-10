"""F2 quantitative comparison channels: measurements, pure engine, native commit."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from .model import LayoutResult


def attach_calibration_errors(
    result: LayoutResult,
    *,
    measured_height_pairs: Sequence[tuple[float, float]],
    reference_border_rectangles: Mapping[str, Mapping[str, float]],
    committed_border_rectangles: Mapping[str, Mapping[str, float]] | None = None,
) -> LayoutResult:
    """Attach independent errors; no observation means unknown (None), not 0."""
    raise NotImplementedError("A10 separated calibration comparison not implemented")
