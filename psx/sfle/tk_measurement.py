"""Tkinter requested-size SFLE measurement, bound to the creating Tk thread.

Tk only exposes requested widget sizes via the public API; this port does
not pretend they are CSS min/max-content metrics for wrapping text.
"""
from __future__ import annotations

import math
import threading
from collections.abc import Mapping
from tkinter import font as tkfont

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class TkMeasurementSource:
    def __init__(
        self, widgets: Mapping[str, object],
        *, textarea_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._widgets = dict(widgets)
        if not textarea_ids <= self._widgets.keys():
            raise ValueError("TextArea measurement IDs must map to mounted Tk controls.")
        self._textarea_ids = textarea_ids
        self._owner_thread = threading.get_ident()

    @staticmethod
    def _textarea_metrics(widget: object, width: float | None) -> IntrinsicSizes:
        """Query the *actual* Tk Text wrapping engine on an isolated widget.

        Measuring the mounted editor by calling place() would mutate its
        geometry, focus, selection and scroll state before SFLE commits.
        This short-lived native probe copies only presentation/text options;
        its display-line count is computed by Tcl/Tk rather than by Python
        approximations of the word-wrap algorithm.
        """
        if width is not None and (
            isinstance(width, bool) or not isinstance(width, (int, float))
            or not math.isfinite(width) or width < 0
        ):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Tk TextArea needs a finite nonnegative content width.")
        font = tkfont.Font(root=widget, font=widget.cget("font"))
        text = widget.get("1.0", "end-1c")
        horizontal = int(widget.cget("padx")) * 2 + (
            int(widget.cget("bd")) + int(widget.cget("highlightthickness"))
        ) * 2
        natural = max(
            (font.measure(line) for line in text.split("\n")), default=0,
        ) + horizontal
        probe_width = max(1, round(width if width is not None else natural))
        options = {
            option: widget.cget(option) for option in (
                "font", "wrap", "padx", "pady", "bd", "relief",
                "highlightthickness", "spacing1", "spacing2", "spacing3",
                "tabs", "tabstyle",
            )
        }
        probe = type(widget)(widget.master, **options)
        try:
            probe.insert("1.0", text)
            probe.place(x=-30000, y=-30000, width=probe_width, height=40)
            probe.update_idletasks()
            count = probe.count("1.0", "end-1c", "displaylines")
            if count is None:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Tk TextArea display-line measurements unavailable.")
            lines = int(count[0]) + 1
            line_height = int(font.metrics("linespace"))
            top_bottom = (
                2 * (int(widget.cget("pady")) +
                     int(widget.cget("bd")) +
                     int(widget.cget("highlightthickness")))
                + int(widget.cget("spacing1")) +
                  int(widget.cget("spacing3"))
            )
            height = max(1, lines) * line_height + top_bottom
            if widget.cget("wrap") == "none":
                height = max(
                    1, text.count("\n") + 1,
                ) * line_height + top_bottom
            return IntrinsicSizes(
                float(natural), float(natural), float(height), float(height),
                float(natural), float(height),
            )
        finally:
            probe.destroy()

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
        if request.node_id in self._textarea_ids:
            metrics = self._textarea_metrics(widget, None)
            return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)
        # On later commits the Text widget may keep a wrapping constraint
        # from the previous SFLE allocation. Take intrinsic hints UNWRAPPED
        # so a previous narrow viewport cannot poison the new inline basis.
        wrap_key = "wraplength" in (widget.keys() if hasattr(widget, "keys") else ())
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
        if node_id in self._textarea_ids:
            return self._textarea_metrics(widget, width)
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
