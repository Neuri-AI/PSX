"""Portable native measurement adapters tested without GUI runtimes."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from psx.sfle.kivy_measurement import KivyMeasurementSource
from psx.sfle.qt_measurement import QtMeasurementSource
from psx.sfle.tk_measurement import TkMeasurementSource
from psx.sfle.errors import SFLEError
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.measurement_round import MeasurementRound
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_measurement import fulfill_native_round


C = LayoutConstraints(AvailableSize(100, True), AvailableSize(None, False))
REQUEST = MeasurementRequest("label", C, 12, 4)
ROUND = MeasurementRound(12, (REQUEST,), (), ("label",))


def test_tk_port_preserves_requested_size_and_rejects_cross_thread():
    widget = SimpleNamespace(winfo_reqwidth=lambda: 42, winfo_reqheight=lambda: 17)
    source = TkMeasurementSource({"label": widget})
    measured, = fulfill_native_round(ROUND, source.port(), current_generation=12)
    assert measured.intrinsic.preferred_width == 42
    assert measured.intrinsic.preferred_height == 17
    with ThreadPoolExecutor(max_workers=1) as worker:
        assert worker.submit(source.is_ui_thread).result() is False
        with pytest.raises(SFLEError):
            worker.submit(fulfill_native_round, ROUND, source.port(), current_generation=12).result()


def test_kivy_port_rejects_unsupported_generic_widget():
    source = KivyMeasurementSource({"label": SimpleNamespace(size=(42, 17))})
    with pytest.raises(SFLEError, match="no known intrinsic"):
        fulfill_native_round(ROUND, source.port(), current_generation=12)


def test_kivy_port_reads_texture_metrics():
    source = KivyMeasurementSource({"label": SimpleNamespace(texture_size=(81, 13))})
    measured, = fulfill_native_round(ROUND, source.port(), current_generation=12)
    assert measured.intrinsic.preferred_width == 81


def test_qt_widget_thread_and_width_sensitive_height():
    current = object()
    qt = SimpleNamespace(QThread=SimpleNamespace(currentThread=lambda: current))
    size = lambda w, h: SimpleNamespace(
        isValid=lambda: True, width=lambda: w, height=lambda: h
    )
    widget = SimpleNamespace(
        thread=lambda: current, sizeHint=lambda: size(50, 12),
        minimumSizeHint=lambda: size(10, 8),
        hasHeightForWidth=lambda: True, heightForWidth=lambda width: width / 2,
    )
    source = QtMeasurementSource({"label": widget}, qtcore=qt)
    measured, = fulfill_native_round(ROUND, source.port(), current_generation=12)
    assert measured.intrinsic.preferred_height == 50
    assert measured.intrinsic.min_content_width == 10


def test_qt_rejects_wrong_widget_thread():
    qt = SimpleNamespace(QThread=SimpleNamespace(currentThread=lambda: object()))
    source = QtMeasurementSource({"label": SimpleNamespace(thread=lambda: object())}, qtcore=qt)
    with pytest.raises(SFLEError, match="UI thread"):
        fulfill_native_round(ROUND, source.port(), current_generation=12)
