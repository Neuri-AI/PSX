"""Qt form controls supply text baselines for native inline flow."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.qt_measurement import QtMeasurementSource


def test_input_and_buttons_share_text_baseline_in_inline_flow():
    app = QApplication.instance() or QApplication(["psx-qt-baseline-test"])
    input_widget = QLineEdit()
    input_widget.setPlaceholderText("Enter new color")
    button_a = QPushButton("Add Color")
    button_b = QPushButton("Clear")
    widgets = {"input": input_widget, "add": button_a, "clear": button_b}
    from PySide6 import QtCore
    source = QtMeasurementSource(widgets, qtcore=QtCore)
    constraints = LayoutConstraints(AvailableSize(500, True), AvailableSize(None, False))
    metrics = {
        name: source.measure(MeasurementRequest(name, constraints, 0, 0)).intrinsic
        for name in widgets
    }
    for name, intrinsic in metrics.items():
        widget = widgets[name]
        expected = ((intrinsic.preferred_height - widget.fontMetrics().height()) / 2
                    + widget.fontMetrics().ascent())
        assert intrinsic.baseline is not None
        assert abs(intrinsic.baseline - expected) <= 1.0
    # All inline atoms should sit on the same textual baseline, without
    # requiring display:flex / align-items:center on the parent div.
    from psx.sfle.flow_layout import InlineAtom, layout_inline_atoms
    atoms = tuple(InlineAtom(m.preferred_width, m.preferred_height, m.baseline)
                  for m in metrics.values())
    places = layout_inline_atoms(500, atoms)
    common = [place.y + atom.baseline for place, atom in zip(places, atoms)]
    assert max(common) - min(common) <= 1 / 64
    for widget in widgets.values():
        widget.deleteLater()
    app.processEvents()
