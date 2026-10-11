"""UI-thread boundary for native intrinsic measurement (F2.2.4.7).

This boundary never imports a GUI framework. Each adapter supplies its own
thread identity check and a synchronous measurement callback. No dispatching
to arbitrary worker threads is permitted by this function.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from .errors import DiagnosticCode, SFLEError
from .measurement_round import MeasurementRound, accept_round
from .measurement_plan import MeasurementRequest
from .model import MeasuredBox

@dataclass(frozen=True, slots=True)
class NativeMeasurementPort:
    """Adapter-owned synchronous UI-thread boundary."""
    is_ui_thread: Callable[[], bool]
    measure: Callable[[MeasurementRequest], MeasuredBox]

def fulfill_native_round(
    round_: MeasurementRound,
    port: NativeMeasurementPort,
    *,
    current_generation: int,
) -> tuple[MeasuredBox, ...]:
    """Measure each request on the renderer UI thread; atomically validate.

    Does not schedule or switch threads. The renderer must call this from its
    UI-thread scheduler; stale/incomplete results are never returned as valid.
    """
    if not isinstance(round_, MeasurementRound) or not isinstance(port, NativeMeasurementPort):
        raise TypeError("Expected MeasurementRound and NativeMeasurementPort.")
    if round_.generation != current_generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale native measurement round.")
    if not port.is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Native measurement requires UI thread.")
    results = []
    for request in round_.requests:
        if not port.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Native measurement left UI thread.")
        if round_.generation != current_generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale native measurement round.")
        result = port.measure(request)
        if not isinstance(result, MeasuredBox):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Native port returned invalid measurement.")
        results.append(result)
    # Reject an incomplete batch without leaking partially accepted results.
    return accept_round(round_, tuple(results), current_generation=current_generation)
