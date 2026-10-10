"""F2 width-dependent measurement session contract (RED phase).

This module intentionally rejects the session until both engines implement
the exact same generation-safe measurement/recompute protocol.
"""
from __future__ import annotations
from collections.abc import Callable
from .model import IntrinsicSizes, LayoutInput, LayoutResult


def compute_with_width_measurements(
    snapshot: LayoutInput,
    compute: Callable[[LayoutInput], LayoutResult],
    measure_fn: Callable[[str, float], IntrinsicSizes],
    *,
    initial_widths: dict[str, float],
    max_rounds: int = 8,
) -> LayoutResult:
    """Coordinate initial and post-flex width-specific text measurements."""
    raise NotImplementedError("F2 width-dependent remeasurement coordination is not implemented")
