"""Missing local image files retain measurable alt-text placeholders."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel
from psx.sfle.qt_measurement import QtMeasurementSource


def test_missing_image_without_intrinsic_dimensions_does_not_abort_cinnamon():
    app = QApplication.instance() or QApplication(["psx-image-measure"])
    widget = QLabel("Logo")
    widget._psx_pixmap_cache = None
    widget._psx_props = {"source": "base/icons/64.png", "alt": "Logo",
                         "width": None, "height": None}
    intrinsic = QtMeasurementSource._image_metrics(widget)
    assert intrinsic.preferred_width > 0
    assert intrinsic.preferred_height > 0
    widget.deleteLater()
