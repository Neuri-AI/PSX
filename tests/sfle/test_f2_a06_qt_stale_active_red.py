"""RED A06: superseded generation halfway through Qt width remeasurement commits nothing."""
import pytest
QtWidgets=pytest.importorskip("PySide6.QtWidgets")
QtCore=pytest.importorskip("PySide6.QtCore")
from dataclasses import replace
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode,SFLEError
from psx.sfle.live_lifecycle import layout_measure_and_commit
from psx.sfle.model import IntrinsicSizes
from test_f2_acceptance_contract_red import case_snapshot


def test_A06_stale_during_real_qt_remeasurement_zero_commits():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent=QtWidgets.QWidget()
    label=QtWidgets.QLabel("x "*18,parent)
    label.setWordWrap(True)
    probe=QtWidgets.QLabel("wrap "*55,parent)
    probe.setWordWrap(True)
    probe.setStyleSheet("font: 10px monospace")
    original_geometry=label.geometry()
    generation=[17]
    calls=[]
    commits=[]
    engine=PythonLayoutEngine()
    def measure(node_id,width):
        assert QtCore.QThread.currentThread()==app.thread()
        value=probe.heightForWidth(round(width))
        calls.append(width)
        if len(calls)==2:
            generation[0]=18
        return IntrinsicSizes(0,210,20,value,width,value)
    try:
        with pytest.raises(SFLEError) as error:
            layout_measure_and_commit(
                replace(case_snapshot("A04"),measurements=()),
                compute=engine.compute,provisional=engine.compute_provisional,
                measure_fn=measure,
                is_ui_thread=lambda:QtCore.QThread.currentThread()==app.thread(),
                current_generation=lambda:generation[0],
                apply_geometry=lambda result:commits.append(result),
                observed_geometry=lambda:{},
                initial_widths={"text":100},
            )
        assert error.value.code==DiagnosticCode.INVALID_SNAPSHOT
        assert calls==pytest.approx([100,150])
        assert commits==[]
        assert label.geometry()==original_geometry
    finally:
        probe.deleteLater()
        label.deleteLater()
        parent.deleteLater()
        app.processEvents()
