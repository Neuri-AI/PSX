"""Kivy intrinsic measurement boundary for SFLE.

Kivy rendering is scheduled on its Clock/UI thread. The caller must create
this source on that thread, and must ensure pending canvas/texture refreshes
have completed before requesting a measurement.
"""
from __future__ import annotations

import math
import threading
from collections.abc import Mapping

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class KivyMeasurementSource:
    def __init__(
        self, widgets: Mapping[str, object],
        *, textarea_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._widgets = dict(widgets)
        if not textarea_ids <= self._widgets.keys():
            raise ValueError("TextArea measurement IDs must map to mounted Kivy controls.")
        self._textarea_ids = textarea_ids
        self._owner_thread = threading.get_ident()

    @staticmethod
    def _textarea_metrics(widget: object, width: float | None) -> IntrinsicSizes:
        """Measure multiline reflow using an isolated native Kivy TextInput.

        TextInput has no label texture_size. Its own minimum_height is based
        on real font glyphs, padding and the wrapped native _lines list.
        The probe is never mounted, so measurement cannot change the live
        editor's cursor, keyboard focus, selection or scroll position.
        """
        if width is not None and (
            isinstance(width, bool) or not isinstance(width, (int, float))
            or not math.isfinite(width) or width < 0
        ):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Kivy TextArea needs a finite nonnegative content width.")
        from kivy.uix.textinput import TextInput
        kwargs = dict(
            text=widget.text, multiline=True, font_name=widget.font_name,
            font_size=widget.font_size, padding=list(widget.padding),
            line_spacing=widget.line_spacing,
            tab_width=widget.tab_width, do_wrap=widget.do_wrap,
            password=widget.password, size_hint=(None, None),
        )
        # Reflow the probe's text using its own native glyph splitter. The
        # explicit refresh is required because Kivy schedules text updates
        # for a later Clock iteration, while SFLE needs a synchronous port.
        probe = TextInput(**kwargs)
        probe.width = float(width) if width is not None else 32768.0
        probe._refresh_text_from_property()
        height = float(probe.minimum_height)
        natural = max(
            (float(label.width) for label in probe._lines_labels),
            default=0.0,
        ) + float(probe.padding[0]) + float(probe.padding[2])
        if not math.isfinite(height) or not math.isfinite(natural):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Kivy TextArea returned nonfinite intrinsic metrics.")
        return IntrinsicSizes(natural, natural, height, height, natural, height)

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
        if request.node_id in self._textarea_ids:
            metrics = self._textarea_metrics(widget, None)
            return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)
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

    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes:
        """Measure a Kivy leaf at the exact post-flex content width."""
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Kivy measurement requires UI thread.")
        widget = self._widgets.get(node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Kivy measurement node.", node_id)
        if node_id in self._textarea_ids:
            return self._textarea_metrics(widget, width)
        previous = getattr(widget, "text_size", None)
        changed = hasattr(widget, "text_size")
        try:
            if changed:
                widget.text_size = (float(width), None)
            refresh = getattr(widget, "texture_update", None)
            if callable(refresh):
                refresh()
            pair = (widget.texture_size if hasattr(widget, "texture_size")
                    else widget.minimum_size if hasattr(widget, "minimum_size") else None)
            if pair is None:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Kivy widget has no width-dependent intrinsic measurement.", node_id)
            measured_width, height = (float(value) for value in pair)
            measured_width = min(float(width), measured_width)
            return IntrinsicSizes(measured_width, measured_width, height, height,
                                  measured_width, height)
        finally:
            if changed:
                widget.text_size = previous
                refresh = getattr(widget, "texture_update", None)
                if callable(refresh):
                    refresh()

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
