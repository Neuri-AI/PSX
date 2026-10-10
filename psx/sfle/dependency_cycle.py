"""F2.2.4.5 synchronous CSS dependency / intrinsic remeasurement loop.

The loop is renderer-independent except for the injected UI-thread measurement
port. The supplied pure resolve pass owns CSS sizing decisions, including
which cyclic percentage cases are valid. No CSS approximations are performed.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from .convergence import RoundStatus, begin_convergence
from .errors import DiagnosticCode, SFLEError
from .measurement_coordinator import complete_measurement_pass
from .measurement_round import prepare_round
from .model import LayoutInput, MeasuredBox
from .native_measurement import NativeMeasurementPort
from .remeasurement import plan_remeasurement
from .used_size_tree import UsedSizeTree


@dataclass(frozen=True, slots=True)
class DependencyResolution:
    used_sizes: UsedSizeTree
    measurements: tuple[MeasuredBox, ...]
    iterations: int


def resolve_measurement_dependencies(
    snapshot: LayoutInput,
    initial_sizes: UsedSizeTree,
    *,
    native_port: NativeMeasurementPort,
    recompute: Callable[[LayoutInput, UsedSizeTree], UsedSizeTree],
    revisions: tuple[tuple[str, int], ...] = (),
    max_iterations: int = 16,
) -> DependencyResolution:
    """Execute a bounded synchronous measurement + pure CSS sizing sequence.

    Called from the UI thread, not from an arbitrary worker. The adapter owns
    the UI-thread check and intrinsic measurement implementation. CSS sizing
    belongs to the injected *pure* recompute callback and must either return a
    new immutable used-size tree or raise an explicit unsupported diagnostic.

    A stable, fully definite sizing snapshot and a fully accepted measurement
    round are jointly required for successful completion. The callback must
    not mutate GUI widgets or request measurements itself.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(initial_sizes, UsedSizeTree):
        raise TypeError("Expected LayoutInput and UsedSizeTree.")
    if not isinstance(native_port, NativeMeasurementPort) or not callable(recompute):
        raise TypeError("Expected NativeMeasurementPort and pure recompute callback.")
    if snapshot.generation != initial_sizes.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Initial size generation mismatch.")
    if tuple(k for k, _ in initial_sizes.content) != tuple(n.node_id for n in snapshot.nodes):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Initial tree ordering mismatch.")
    if not native_port.is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Resolution requires renderer UI thread.")

    state = begin_convergence(initial_sizes, max_iterations=max_iterations)
    current = initial_sizes
    previous = initial_sizes
    measured = snapshot.measurements
    for _ in range(max_iterations):
        # A previous pass's accepted snapshots are available for exact
        # constraint/revision reuse, but never as a substitute for recompute.
        generation_snapshot = replace(snapshot, measurements=measured)
        delta = plan_remeasurement(generation_snapshot, previous, current)
        round_ = prepare_round(
            generation_snapshot, delta,
            constraints=current.content, revisions=revisions,
        )
        if not native_port.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "UI thread changed during resolution.")
        native_results_list = []
        for request in round_.requests:
            if not native_port.is_ui_thread():
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Native measurement left UI thread.")
            native_results_list.append(native_port.measure(request))
        native_results = tuple(native_results_list)
        # Acceptance must occur before the pure CSS size recomputation, and
        # no partial results are exposed on invalid revisions/generations.
        from .measurement_round import accept_round
        accepted = accept_round(round_, native_results, current_generation=snapshot.generation)
        next_snapshot = replace(snapshot, measurements=accepted)
        updated = recompute(next_snapshot, current)
        if not isinstance(updated, UsedSizeTree):
            raise TypeError("Recompute must return UsedSizeTree.")
        transition = complete_measurement_pass(
            state, round_, native_results, updated,
            current_generation=snapshot.generation,
        )
        if transition.status == RoundStatus.CONVERGED:
            return DependencyResolution(updated, accepted, transition.convergence.iterations)
        state = transition.convergence
        measured = accepted
        previous, current = current, updated
    raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Measurement pass limit exceeded.")
