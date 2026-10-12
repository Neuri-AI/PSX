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
        # On later commits the Text widget may keep a wrapping constraint
        # from the previous SFLE allocation. Take intrinsic hints UNWRAPPED
        # so a previous narrow viewport cannot poison the new inline basis.
        wrap_key = "wraplength" in widget.keys()
        old_wrap = widget.cget("wraplength") if wrap_key else None
        try:
            if wrap_key:
                widget.configure(wraplength=0)
                widget.update_idletasks()
            width = float(widget.winfo_reqwidth())
            height = float(widget.winfo_reqheight())
        finally:
            if wrap_key:
                widget.configure(wraplength=old_wrap)
                widget.update_idletasks()
        if width < 0 or height < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid Tk requested widget size.")
        metrics = IntrinsicSizes(
            min_content_width=width, max_content_width=width,
            min_content_height=height, max_content_height=height,
            preferred_width=width, preferred_height=height,
        )
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes:
        """Measure a Tk leaf after applying a temporary wrapping constraint."""
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Tk measurement requires its owning thread.")
        widget = self._widgets.get(node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Tk measurement node.", node_id)
        previous = None
        wraps = False
        try:
            keys = widget.keys() if hasattr(widget, "keys") else ()
            wraps = "wraplength" in keys
            if wraps:
                previous = widget.cget("wraplength")
                widget.configure(wraplength=max(0, round(width)))
            widget.update_idletasks()
            measured_width = min(float(width), float(widget.winfo_reqwidth()))
            height = float(widget.winfo_reqheight())
            return IntrinsicSizes(measured_width, measured_width, height, height,
                                  measured_width, height)
        finally:
            if wraps:
                widget.configure(wraplength=previous)
                widget.update_idletasks()

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
