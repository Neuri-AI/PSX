"""Independent F2 measurement, pure engine and native commit errors.

Unknown observations remain None. No native geometry may be inferred from a
browser comparison; a native commit is a separately supplied observation.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace

from .model import LayoutResult


def attach_calibration_errors(
    result: LayoutResult,
    *,
    measured_height_pairs: Sequence[tuple[float, float]],
    reference_border_rectangles: Mapping[str, Mapping[str, float]],
    committed_border_rectangles: Mapping[str, Mapping[str, float]] | None = None,
) -> LayoutResult:
    """Attach independent maximum absolute errors (logical CSS pixels).

    Measurement compares independent predicted vs observed DOM heights.
    Engine compares pure SFLE border geometry vs independent browser border.
    Commit compares native widget border geometry vs pure SFLE output.
    """
    if not isinstance(result, LayoutResult):
        raise TypeError("Expected LayoutResult.")
    boxes = dict(result.boxes)
    axes = ("x", "y", "width", "height")

    def difference(a: float, b: float) -> float:
        if any(isinstance(v, bool) or not isinstance(v, (float, int))
               or not math.isfinite(v) for v in (a, b)):
            raise ValueError("Calibrated values must be finite CSS pixel numbers.")
        return abs(a - b)

    measurement = (
        max(difference(expected, observed) for expected, observed in measured_height_pairs)
        if measured_height_pairs else None
    )

    def compare(rectangles: Mapping[str, Mapping[str, float]]) -> float | None:
        if not rectangles:
            return None
        errors = []
        for node_id, rect in rectangles.items():
            if node_id not in boxes:
                raise ValueError(f"Unknown calibration node: {node_id}.")
            expected = boxes[node_id].border
            errors.extend(difference(getattr(expected, axis), rect[axis]) for axis in axes)
        return max(errors)

    return replace(
        result,
        measurement_error=measurement,
        engine_error=compare(reference_border_rectangles),
        geometry_commit_error=(
            compare(committed_border_rectangles)
            if committed_border_rectangles is not None else None
        ),
    )
