"""Kivy intrinsic measurement boundary for SFLE.

Kivy rendering is scheduled on its Clock/UI thread. The caller must create
this source on that thread, and must ensure pending canvas/texture refreshes
have completed before requesting a measurement.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class KivyMeasurementSource:
    def __init__(self, widgets: Mapping[str, object]) -> None:
        self._widgets = dict(widgets)
        self._owner_thread = threading.get_ident()

    def is_ui_thread(self) -> bool:
        return threading.get_ident() == self._owner_thread

    def measure(self, request: MeasurementRequest) -> MeasuredBox:
        if not isinstance(request, MeasurementRequest):
            raise TypeError("Expected MeasurementRequest.")
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Kivy measurement requires UI thread.")
        widget = self._widgets.get(request.node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Kivy measurement node.")
        # texture_size is the measured pixel content for Kivy Label.
        # minimum_size is available on some Kivy layouts. A generic Widget's
        # size is a negotiated allocation, not a valid intrinsic measurement.
        if hasattr(widget, "texture_size"):
            pair = widget.texture_size
        elif hasattr(widget, "minimum_size"):
            pair = widget.minimum_size
        else:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Kivy widget has no known intrinsic measurement (texture/minimum size).",
            )
        width, height = (float(v) for v in pair)
        if width < 0 or height < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid Kivy intrinsic metrics.")
        metrics = IntrinsicSizes(width, width, height, height, width, height)
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
