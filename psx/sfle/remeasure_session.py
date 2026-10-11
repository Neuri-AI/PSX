"""Generation-scoped active post-flex measurement coordinator.

A renderer calls this coordinator on the UI thread through its measurement
adapter. Both pure engines receive identical immutable snapshots, and no
native measurement is fabricated from their layout output.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from .errors import DiagnosticCode, SFLEError
from .model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutResult, MeasuredBox,
)


def compute_with_width_measurements(
    snapshot: LayoutInput,
    compute: Callable[[LayoutInput], LayoutResult],
    measure_fn: Callable[[str, float], IntrinsicSizes],
    *,
    compute_provisional: Callable[[LayoutInput], LayoutResult],
    initial_widths: dict[str, float],
    max_rounds: int = 8,
) -> LayoutResult:
    """Measure initial leaf hints, then measure again at allocated widths.

    Every transition uses a new immutable input snapshot, validates generation
    and leaf identity, and converges only when all measured widths equal the
    current final allocated content widths. Oscillating widths/metrics fail.
    This pure coordinator does not itself commit geometry.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("Expected LayoutInput.")
    if max_rounds < 1:
        raise ValueError("max_rounds must be positive.")
    if not callable(compute) or not callable(compute_provisional) or not callable(measure_fn):
        raise TypeError("Expected compute and UI-thread measure callbacks.")
    nodes = {n.node_id for n in snapshot.nodes}
    if not initial_widths or not set(initial_widths).issubset(nodes):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                        "Measurement leaves must be present in the tree.")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0
           for v in initial_widths.values()):
        raise ValueError("Measurement widths must be positive finite values.")
    measurements: dict[str, MeasuredBox] = {
        item.node_id: item for item in snapshot.measurements
        if item.node_id not in initial_widths
    }
    # Every leaf stays in the convergence check; a sibling can change its
    # allocation after another item's new intrinsic measurement.
    measured_widths = dict(initial_widths)
    requested_widths = dict(initial_widths)
    seen: set[tuple[tuple[str, float], ...]] = set()
    for iteration in range(max_rounds):
        signature = tuple(sorted(measured_widths.items()))
        if signature in seen:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Post-flex width measurement oscillation; no geometry committed.",
            )
        seen.add(signature)
        for node_id, width in requested_widths.items():
            intrinsic = measure_fn(node_id, width)
            if not isinstance(intrinsic, IntrinsicSizes):
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                    "Measure callback did not return normalized intrinsic sizes.",
                    node_id,
                )
            measurements[node_id] = MeasuredBox(
                node_id,
                intrinsic,
                LayoutConstraints(
                    AvailableSize(float(width), True),
                    AvailableSize(intrinsic.preferred_height, True),
                ),
                iteration,
            )
        request = replace(snapshot, measurements=tuple(measurements.values()))
        result = compute_provisional(request) if iteration == 0 else compute(request)
        if result.generation != snapshot.generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Engine returned a stale generation.")
        used = dict(result.boxes)
        next_widths = {}
        for node_id, width in measured_widths.items():
            if node_id not in used:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Measured leaf missing from layout output.",node_id)
            allocated_width = used[node_id].content.width
            if abs(allocated_width-width) > 0.01:
                next_widths[node_id] = allocated_width
        if not next_widths:
            return result
        requested_widths = next_widths
        measured_widths.update(next_widths)
    raise SFLEError(
        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
        "Post-flex width measurement did not converge within the iteration budget.",
    )
