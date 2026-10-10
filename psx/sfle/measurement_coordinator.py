"""Pure coordinator connecting accepted measurement rounds to convergence.

The caller performs CSS used-size recomputation and UI-thread measurements.
This module only enforces generations, complete results, and round sequencing.
"""
from __future__ import annotations
from dataclasses import dataclass
from .convergence import ConvergenceState, RoundStatus, advance_convergence
from .errors import DiagnosticCode, SFLEError
from .measurement_round import MeasurementRound, accept_round
from .model import MeasuredBox
from .used_size_tree import UsedSizeTree

@dataclass(frozen=True, slots=True)
class RoundTransition:
    status: RoundStatus
    convergence: ConvergenceState
    measurements: tuple[MeasuredBox, ...]

def complete_measurement_pass(
    state: ConvergenceState,
    round_: MeasurementRound,
    results: tuple[MeasuredBox, ...],
    updated_tree: UsedSizeTree,
    *,
    current_generation: int,
) -> RoundTransition:
    """Accept all measurements before considering the next CSS sizing pass.

    A stable used-size tree may be declared converged only when there are
    no deferred axes. A future CSS geometry pass is responsible for proving
    that used-size snapshots correspond to the accepted intrinsic metrics.
    """
    if current_generation != state.generation or round_.generation != state.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Cross-generation measurement pass.")
    measured = accept_round(round_, results, current_generation=current_generation)
    status, next_state = advance_convergence(state, updated_tree)
    if status == RoundStatus.CONVERGED and round_.deferred:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Convergence cannot retain deferred axes.")
    return RoundTransition(status, next_state, measured)
