"""RED: native QLabel measurement may never run on a worker thread.

A pure compute callback may run on a worker, but the existing synchronous
renderer lifecycle must reject its attempt to measure through that thread.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest
QtWidgets=pytest.importorskip("PySide6.QtWidgets")
QtCore=pytest.importorskip("PySide6.QtCore")
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError,DiagnosticCode
from psx.sfle.live_lifecycle import layout_measure_and_commit
from test_f2_acceptance_contract_red import case_snapshot


def test_qt_worker_compute_must_dispatch_measurement_to_ui_or_reject():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget=QtWidgets.QLabel("real Qt text")
    calls=[]
    engine=PythonLayoutEngine()
    def unsafe_measure(node_id,width):
        calls.append(QtCore.QThread.currentThread())
        raise AssertionError("worker must never invoke Qt measurement")
    def worker():
        return layout_measure_and_commit(
            replace(case_snapshot("A04"),measurements=()),
            compute=engine.compute,
            provisional=engine.compute_provisional,
            measure_fn=unsafe_measure,
            is_ui_thread=lambda:QtCore.QThread.currentThread()==app.thread(),
            current_generation=lambda:17,
            apply_geometry=lambda result:pytest.fail("worker committed geometry"),
            observed_geometry=lambda:{},
            initial_widths={"text":100},
        )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(worker)
            with pytest.raises(SFLEError) as error:
                future.result(timeout=5)
        assert error.value.code==DiagnosticCode.UNSUPPORTED_MEASUREMENT
        assert calls==[]
    finally:
        widget.deleteLater()
        app.processEvents()
