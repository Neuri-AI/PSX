"""Bounded sizing passes must never substitute oscillation for CSS sizing."""
import pytest
from psx.sfle.errors import SFLEError
from psx.sfle.convergence import RoundStatus, begin_convergence, advance_convergence
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.used_size_tree import UsedSizeTree

def tree(generation=8, width=100):
    return UsedSizeTree(generation, (("root", LayoutConstraints(
        AvailableSize(width, width is not None), AvailableSize(20, True),
    )),), ())

def test_stable_definite_snapshot_converges():
    status, state = advance_convergence(begin_convergence(tree()), tree())
    assert status is RoundStatus.CONVERGED
    assert state.iterations == 1

def test_unresolved_unchanged_snapshot_does_not_false_converge():
    with pytest.raises(SFLEError):
        advance_convergence(begin_convergence(tree(width=None)), tree(width=None))

def test_two_step_oscillation_is_rejected():
    _, state = advance_convergence(begin_convergence(tree()), tree(width=120))
    with pytest.raises(SFLEError):
        advance_convergence(state, tree())

def test_generation_mismatch_and_limit_rejected():
    with pytest.raises(SFLEError):
        advance_convergence(begin_convergence(tree()), tree(generation=9))
    with pytest.raises(SFLEError):
        advance_convergence(begin_convergence(tree(), max_iterations=1), tree(width=120))
