"""Bounded measurement-convergence bookkeeping for SFLE F2.2.4.5.

This is a pure state transition, not a CSS fixed-point solver. Only a caller
that has already established CSS-valid sizing semantics may advance a round.
Repeating identical unresolved constraints is not evidence of convergence.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .errors import DiagnosticCode, SFLEError
from .used_size_tree import UsedSizeTree

class RoundStatus(str, Enum):
    CONTINUE = "continue"
    CONVERGED = "converged"

@dataclass(frozen=True, slots=True)
class ConvergenceState:
    generation: int
    iterations: int
    previous: UsedSizeTree
    history: tuple[tuple[tuple[str, object], ...], ...]
    max_iterations: int = 16

def begin_convergence(tree: UsedSizeTree, *, max_iterations: int = 16) -> ConvergenceState:
    if not isinstance(tree, UsedSizeTree) or type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("Valid used-size tree and positive iteration limit required.")
    return ConvergenceState(tree.generation, 0, tree, (tree.content,), max_iterations)

def advance_convergence(
    state: ConvergenceState, current: UsedSizeTree
) -> tuple[RoundStatus, ConvergenceState]:
    """Advance after a complete measurement/layout pass.

    An unchanged *definite* snapshot converges. Repeated unresolved snapshots
    and multi-step cycles fail closed rather than guessing a CSS used value.
    """
    if not isinstance(state, ConvergenceState) or not isinstance(current, UsedSizeTree):
        raise TypeError("Expected convergence state and used-size tree.")
    if current.generation != state.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale convergence generation.")
    if tuple(k for k, _ in current.content) != tuple(k for k, _ in state.previous.content):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Convergence node identity changed.")
    if state.iterations >= state.max_iterations:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Measurement iteration limit reached.")
    iterations = state.iterations + 1
    definite = all(
        value.width.definite and value.height.definite for _, value in current.content
    )
    if current.content == state.previous.content and definite:
        return RoundStatus.CONVERGED, ConvergenceState(
            state.generation, iterations, current, state.history, state.max_iterations
        )
    if current.content in state.history:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "Repeated unresolved constraints or measurement dependency cycle.",
        )
    if iterations >= state.max_iterations:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Measurement iteration limit reached.")
    return RoundStatus.CONTINUE, ConvergenceState(
        state.generation, iterations, current,
        state.history + (current.content,), state.max_iterations
    )
