"""B1 acceptance: real Qt UI measurement, worker compute and observed geometry."""

from dataclasses import replace
import threading
import time

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.qt_measurement import QtMeasurementSource
from psx.sfle.worker_lifecycle import start_native_worker_layout
from test_f2_acceptance_contract_red import case_snapshot


def test_qt_live_label_remeasures_and_readback_commits_real_widget():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    parent.resize(150, 300)
    label = QtWidgets.QLabel("wrap " * 55, parent)
    label.setWordWrap(True)
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
    font = label.font()
    font.setFamily("DejaVu Sans Mono")
    font.setPixelSize(10)
    label.setFont(font)
    parent.show()
    label.show()

    snapshot = replace(case_snapshot("A04"), measurements=())
    engine = PythonLayoutEngine()
    source = QtMeasurementSource({"text": label}, qtcore=QtCore)
    ui_thread = threading.get_ident()
    computed = []
    measured = []
    committed = []
    outcomes = []
    generation = [snapshot.generation]

    def worker(data, method):
        computed.append(threading.get_ident())
        assert threading.get_ident() != ui_thread
        return method(data)

    def measure_ui(node_id, width):
        assert threading.get_ident() == ui_thread
        request = MeasurementRequest(
            node_id, LayoutConstraints(
                AvailableSize(width, True), AvailableSize(None, False),
            ), generation[0], 0,
        )
        measured.append((width, threading.get_ident()))
        return source.port().measure(request).intrinsic

    def observed():
        assert threading.get_ident() == ui_thread
        rect = label.geometry()
        return {"text": {
            "x": float(rect.x()), "y": float(rect.y()),
            "width": float(rect.width()), "height": float(rect.height()),
        }}

    def apply(result):
        assert threading.get_ident() == ui_thread
        rect = dict(result.boxes)["text"].border
        label.setGeometry(round(rect.x), round(rect.y), round(rect.width), round(rect.height))
        committed.append(result.generation)

    def restore(original):
        assert threading.get_ident() == ui_thread
        rect = original["text"]
        label.setGeometry(*(round(rect[k]) for k in ("x", "y", "width", "height")))

    try:
        handle = start_native_worker_layout(
            snapshot,
            compute=lambda data: worker(data, engine.compute),
            provisional=lambda data: worker(data, engine.compute_provisional),
            measure_on_ui=measure_ui,
            is_ui_thread=source.port().is_ui_thread,
            current_generation=lambda: generation[0],
            apply_geometry=apply,
            observed_geometry=observed,
            restore_geometry=restore,
            initial_widths={"text": 100.0},
            post_to_ui=lambda callback: QtCore.QTimer.singleShot(1, callback),
            on_finished=lambda result, error: outcomes.append((result, error)),
            nodes_alive=lambda ids: set(ids) == {"root", "text"} and label.parent() is parent,
        )
        deadline = time.monotonic() + 8
        while not outcomes and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.001)
        assert len(outcomes) == 1, "Qt worker did not complete"
        result, error = outcomes[0]
        assert error is None, repr(error)
        assert result is not None and handle.done()
        assert len(measured) >= 2
        assert measured[0][0] == 100
        assert measured[-1][0] == 150
        assert all(t == ui_thread for _, t in measured)
        assert computed and all(t != ui_thread for t in computed)
        assert committed == [snapshot.generation]
        assert result.geometry_commit_error is not None
        assert result.geometry_commit_error <= 1.0
        assert observed()["text"]["width"] == 150.0
    finally:
        parent.close()
        parent.deleteLater()
        app.processEvents()
