"""Tkinter requested-size SFLE measurement, bound to the creating Tk thread.

Tk only exposes requested widget sizes via the public API; this port does
not pretend they are CSS min/max-content metrics for wrapping text.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class TkMeasurementSource:
    def __init__(self, widgets: Mapping[str, object]) -> None:
        self._widgets = dict(widgets)
        self._owner_thread = threading.get_ident()

    def is_ui_thread(self) -> bool:
        return threading.get_ident() == self._owner_thread

    def measure(self, request: MeasurementRequest) -> MeasuredBox:
        if not isinstance(request, MeasurementRequest):
            raise TypeError("Expected MeasurementRequest.")
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Tk measurement requires its owning thread.")
        widget = self._widgets.get(request.node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Tk measurement node.")
        width = float(widget.winfo_reqwidth())
        height = float(widget.winfo_reqheight())
        if width < 0 or height < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid Tk requested widget size.")
        metrics = IntrinsicSizes(
            min_content_width=width, max_content_width=width,
            min_content_height=height, max_content_height=height,
            preferred_width=width, preferred_height=height,
        )
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
