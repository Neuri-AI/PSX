"""RED A04: real wrapped QLabel must remeasure and commit with real error."""
import pytest
QtWidgets=pytest.importorskip("PySide6.QtWidgets")
QtCore=pytest.importorskip("PySide6.QtCore")
from dataclasses import replace
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.live_lifecycle import layout_measure_and_commit
from psx.sfle.model import IntrinsicSizes
from test_acceptance_contract_regression import case_snapshot


def test_A04_qt_real_wrap_measures_twice_and_commits_final_geometry():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent=QtWidgets.QWidget()
    label=QtWidgets.QLabel("wrap "*55,parent)
    label.setWordWrap(True)
    font=QtWidgets.QApplication.font()
    font.setFamily("DejaVu Sans Mono")
    font.setPixelSize(10)
    label.setFont(font)
    calls=[]
    commits=[]
    engine=PythonLayoutEngine()
    def measure(node_id,width):
        assert QtCore.QThread.currentThread()==app.thread()
        label.setFixedWidth(round(width))
        height=label.heightForWidth(round(width))
        calls.append((width,height))
        return IntrinsicSizes(0,210,20,height,width,height)
    def apply(result):
        assert QtCore.QThread.currentThread()==app.thread()
        rect=dict(result.boxes)["text"].border
        label.setGeometry(round(rect.x),round(rect.y),round(rect.width),round(rect.height))
        commits.append(result)
    def observed():
        rect=label.geometry()
        return {"text":{"x":rect.x(),"y":rect.y(),"width":rect.width(),"height":rect.height()}}
    try:
        result=layout_measure_and_commit(
            replace(case_snapshot("A04"),measurements=()),
            compute=engine.compute,provisional=engine.compute_provisional,
            measure_fn=measure,
            is_ui_thread=lambda:QtCore.QThread.currentThread()==app.thread(),
            current_generation=lambda:17,
            apply_geometry=apply,observed_geometry=observed,
            initial_widths={"text":100},
        )
        assert [width for width,_ in calls]==pytest.approx([100,150])
        assert calls[0][1]>calls[1][1]
        assert len(commits)==1
        assert label.geometry().height()==pytest.approx(calls[-1][1],abs=1)
        assert result.geometry_commit_error is not None, "Native geometry was observed, not inferred"
        assert 0.0 <= result.geometry_commit_error <= 1.0, (
            f"D-F1.11 Qt geometry_commit_error={result.geometry_commit_error}px"
        )
        assert result.measurement_error is None, "No independent browser intrinsic oracle here"
        assert result.engine_error is None, "No independent Chromium geometry oracle here"
        committed = dict(result.boxes)["text"].border
        observed_rect = label.geometry()
        for axis, expected, applied in (
            ("x", committed.x, observed_rect.x()),
            ("y", committed.y, observed_rect.y()),
            ("width", committed.width, observed_rect.width()),
            ("height", committed.height, observed_rect.height()),
        ):
            assert abs(expected - applied) <= 1.0, f"Qt {axis}: engine={expected}, native={applied}"

    finally:
        label.deleteLater()
        parent.deleteLater()
        app.processEvents()
