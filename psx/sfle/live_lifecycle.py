"""Generation-safe, UI-thread-only width-sensitive native layout lifecycle.

The adapter owns real widget measurements and commit. The pure coordinator
owns the provisional/final sizing protocol; neither may commit a provisional
layout or apply geometry after the captured generation becomes obsolete.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

from .calibration import attach_calibration_errors
from .errors import DiagnosticCode, SFLEError
from .model import IntrinsicSizes, LayoutInput, LayoutResult
from .remeasure_session import compute_with_width_measurements


def layout_measure_and_commit(
    snapshot: LayoutInput,
    *,
    compute: Callable[[LayoutInput], LayoutResult],
    provisional: Callable[[LayoutInput], LayoutResult],
    measure_fn: Callable[[str, float], IntrinsicSizes],
    is_ui_thread: Callable[[], bool],
    current_generation: Callable[[], int],
    apply_geometry: Callable[[LayoutResult], None],
    observed_geometry: Callable[[], Mapping[str, Mapping[str, float]]],
    initial_widths: dict[str, float],
) -> LayoutResult:
    """Atomically guard a measured layout transaction and observe committed boxes.

    `apply_geometry` must be an adapter-atomic operation, not a per-node
    callback. A check immediately before the single commit prevents any
    outdated transaction from mutating native geometry.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("Expected an immutable LayoutInput.")
    functions = (compute, provisional, measure_fn, is_ui_thread,
                 current_generation, apply_geometry, observed_geometry)
    if not all(callable(value) for value in functions):
        raise TypeError("Lifecycle must supply all mandatory callbacks.")
    generation = snapshot.generation

    def require_live(phase: str) -> None:
        if not is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            f"Native SFLE {phase} requires the UI thread.")
        if current_generation() != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            f"Stale SFLE generation during {phase}; no commit.")

    require_live("start")

    def checked_measure(node_id: str, width: float) -> IntrinsicSizes:
        require_live("before measurement")
        result = measure_fn(node_id, width)
        require_live("after measurement")
        return result

    def checked_provisional(request: LayoutInput) -> LayoutResult:
        require_live("before provisional computation")
        result = provisional(request)
        require_live("after provisional computation")
        return result

    def checked_compute(request: LayoutInput) -> LayoutResult:
        require_live("before final computation")
        result = compute(request)
        require_live("after final computation")
        return result

    final = compute_with_width_measurements(
        snapshot, checked_compute, checked_measure,
        initial_widths=initial_widths, compute_provisional=checked_provisional,
    )
    require_live("before geometry commit")
    if final.generation != generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                        "Computed geometry belongs to an obsolete generation.")
    apply_geometry(final)
    require_live("after geometry commit")
    observed = observed_geometry()
    require_live("after native geometry observation")
    return attach_calibration_errors(
        final, measured_height_pairs=(),
        reference_border_rectangles={},
        committed_border_rectangles=observed,
    )
