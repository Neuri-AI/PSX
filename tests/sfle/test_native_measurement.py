"""Native protocol test double verifies UI-thread and batch contracts."""
import pytest
from psx.sfle.errors import SFLEError
from psx.sfle.measurement_round import MeasurementRound
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from psx.sfle.native_measurement import NativeMeasurementPort, fulfill_native_round

C = LayoutConstraints(AvailableSize(100, True), AvailableSize(None, False))
R = MeasurementRound(8, (MeasurementRequest("leaf", C, 8, 2),), (), ("leaf",))
M = IntrinsicSizes(1, 2, 3, 4, 2, 4)

def test_native_port_invoked_once_on_ui_thread():
    seen = []
    port = NativeMeasurementPort(lambda: True, lambda r: (
        seen.append(r.node_id) or MeasuredBox(r.node_id, M, r.constraints, r.revision)
    ))
    assert fulfill_native_round(R, port, current_generation=8)[0].revision == 2
    assert seen == ["leaf"]

def test_non_ui_thread_rejected_without_invoking_native_measurer():
    port = NativeMeasurementPort(lambda: False, lambda _: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(SFLEError):
        fulfill_native_round(R, port, current_generation=8)

def test_generation_and_revision_mismatch_rejected():
    port = NativeMeasurementPort(lambda: True, lambda r: MeasuredBox(r.node_id, M, r.constraints, 1))
    with pytest.raises(SFLEError):
        fulfill_native_round(R, port, current_generation=8)
    with pytest.raises(SFLEError):
        fulfill_native_round(R, port, current_generation=9)
