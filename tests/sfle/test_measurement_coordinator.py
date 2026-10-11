"""Coordinator must validate native results before any convergence transition."""
import pytest
from psx.sfle.convergence import RoundStatus, begin_convergence
from psx.sfle.errors import SFLEError
from psx.sfle.measurement_coordinator import complete_measurement_pass
from psx.sfle.measurement_round import MeasurementRound
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from psx.sfle.used_size_tree import UsedSizeTree

CONSTRAINT = LayoutConstraints(AvailableSize(100, True), AvailableSize(20, True))
TREE = UsedSizeTree(8, (("root", CONSTRAINT),), ())
REQUEST = MeasurementRequest("root", CONSTRAINT, 8, 0)
ROUND = MeasurementRound(8, (REQUEST,), (), ())

def test_complete_round_converges_after_acceptance():
    measured = MeasuredBox("root", IntrinsicSizes(1, 1, 1, 1, 1, 1), CONSTRAINT, 0)
    result = complete_measurement_pass(begin_convergence(TREE), ROUND, (measured,), TREE, current_generation=8)
    assert result.status is RoundStatus.CONVERGED
    assert result.measurements == (measured,)

def test_incomplete_and_stale_results_cannot_advance():
    with pytest.raises(SFLEError):
        complete_measurement_pass(begin_convergence(TREE), ROUND, (), TREE, current_generation=8)
    with pytest.raises(SFLEError):
        complete_measurement_pass(begin_convergence(TREE), ROUND, (), TREE, current_generation=9)
