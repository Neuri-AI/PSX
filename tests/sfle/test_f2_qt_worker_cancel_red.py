"""RED: explicit cancellation must invalidate queued Qt worker measurements."""
from dataclasses import replace
import time
import pytest
QtWidgets=pytest.importorskip("PySide6.QtWidgets")
QtCore=pytest.importorskip("PySide6.QtCore")
from psx.sfle.qt_worker_dispatch import start_qt_worker_layout
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from psx.sfle.model import IntrinsicSizes
from test_f2_acceptance_contract_red import case_snapshot


def test_qt_worker_explicit_cancel_queued_measurement_never_commits():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    engine=PythonLayoutEngine()
    measured=[]
    commits=[]
    outcomes=[]
    handle=start_qt_worker_layout(
        replace(case_snapshot("A04"),measurements=()),
        qtcore=QtCore,
        compute=engine.compute,
        provisional=engine.compute_provisional,
        measure_on_ui=lambda name,width: (
            measured.append((name,width))
            or IntrinsicSizes(0,210,20,40,width,40)
        ),
        current_generation=lambda:17,
        commit_on_ui=lambda result:commits.append(result),
        initial_widths={"text":100},
        on_finished=lambda result,error:outcomes.append((result,error)),
    )
    handle.cancel()
    deadline=time.monotonic()+5
    while not outcomes and time.monotonic()<deadline:
        app.processEvents()
        time.sleep(0.001)
    assert len(outcomes)==1, "Cancel must release worker without UI deadlock"
    result,error=outcomes[0]
    assert result is None
    assert isinstance(error,SFLEError)
    assert error.code==DiagnosticCode.INVALID_SNAPSHOT
    assert measured==[]
    assert commits==[]
    assert handle.done()
