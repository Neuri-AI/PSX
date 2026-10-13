"""RED: background F2 compute must leave Qt event loop live and GUI measurements on UI."""
from dataclasses import replace
import time
import threading
import pytest
QtWidgets=pytest.importorskip("PySide6.QtWidgets")
QtCore=pytest.importorskip("PySide6.QtCore")
from psx.sfle.qt_worker_dispatch import start_qt_worker_layout
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import IntrinsicSizes
from test_acceptance_contract_regression import case_snapshot


def test_qt_worker_compute_async_measurement_and_atomic_commit():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    label=QtWidgets.QLabel("wrap " * 55)
    label.setWordWrap(True)
    font = QtWidgets.QApplication.font()
    font.setFamily("DejaVu Sans Mono")
    font.setPixelSize(10)
    label.setFont(font)
    ui_thread = threading.get_ident()
    pure_compute_threads = []
    measured_heights = []
    def compute_on_worker(snapshot):
        pure_compute_threads.append(threading.get_ident())
        assert threading.get_ident() != ui_thread, "Pure SFLE must not block Qt UI"
        return engine.compute(snapshot)
    def provisional_on_worker(snapshot):
        pure_compute_threads.append(threading.get_ident())
        assert threading.get_ident() != ui_thread
        return engine.compute_provisional(snapshot)
    engine=PythonLayoutEngine()
    calls=[]
    commits=[]
    outcomes=[]
    heartbeat=[]
    generation=[17]
    def measure(node_id,width):
        assert QtCore.QThread.currentThread()==app.thread()
        assert threading.get_ident()==ui_thread
        calls.append((node_id,width))
        h=label.heightForWidth(round(width))
        measured_heights.append(h)
        return IntrinsicSizes(0,210,20,h,width,h)
    def commit(result):
        assert QtCore.QThread.currentThread()==app.thread()
        commits.append(result)
    timer=QtCore.QTimer()
    timer.timeout.connect(lambda:heartbeat.append(True))
    timer.start(1)
    try:
        handle=start_qt_worker_layout(
            replace(case_snapshot("A04"),measurements=()),
            qtcore=QtCore,compute=compute_on_worker,provisional=provisional_on_worker,
            measure_on_ui=measure,current_generation=lambda:generation[0],
            commit_on_ui=commit,initial_widths={"text":100},
            on_finished=lambda result,error:outcomes.append((result,error)),
        )
        deadline=time.monotonic()+5
        while not outcomes and time.monotonic()<deadline:
            app.processEvents()
            time.sleep(0.001)
        assert len(outcomes)==1, "Async worker must finish without GUI deadlock"
        result,error=outcomes[0]
        assert error is None
        assert result is not None
        assert [name for name,_ in calls]==["text","text"]
        assert [width for _,width in calls]==pytest.approx([100,150])
        assert len(commits)==1
        assert pure_compute_threads and all(t != ui_thread for t in pure_compute_threads)
        assert measured_heights[0] >= measured_heights[-1], "Wider text must not wrap into more lines"
        assert heartbeat, "Qt event loop must process unrelated GUI events"
        assert getattr(handle,"done",lambda:False)()
    finally:
        timer.stop()
        label.deleteLater()
        app.processEvents()
