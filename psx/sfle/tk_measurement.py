"""Tkinter requested-size SFLE measurement, bound to the creating Tk thread.

Tk only exposes requested widget sizes via the public API; this port does
not pretend they are CSS min/max-content metrics for wrapping text.
"""
from __future__ import annotations

import math
import threading
from dataclasses import replace
from collections.abc import Mapping

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class TkMeasurementSource:
    def __init__(
        self, widgets: Mapping[str, object],
        *, textarea_ids: frozenset[str] = frozenset(),
        image_ids: frozenset[str] = frozenset(),
        spacer_ids: frozenset[str] = frozenset(),
        divider_nodes: Mapping[str, object] | None = None,
        idle_synced: bool = False,
    ) -> None:
        self._widgets = dict(widgets)
        if not textarea_ids <= self._widgets.keys():
            raise ValueError("TextArea measurement IDs must map to mounted Tk controls.")
        self._textarea_ids = textarea_ids
        if not image_ids <= self._widgets.keys():
            raise ValueError("Image measurement IDs must refer to mounted Tk controls.")
        self._image_ids = image_ids
        if not spacer_ids <= self._widgets.keys():
            raise ValueError("Spacer measurement IDs must refer to native widgets.")
        self._spacer_ids = spacer_ids
        self._divider_nodes = dict(divider_nodes or {})
        if not self._divider_nodes.keys() <= self._widgets.keys():
            raise ValueError("Divider IDs must refer to native widgets.")
        self._owner_thread = threading.get_ident()
        # Only the Grid bridge may opt in after an owner-thread idle drain.
        self._idle_synced = idle_synced

    @staticmethod
    def _structural_metrics(kind: str, props: Mapping[str, object]) -> IntrinsicSizes:
        if kind == "Spacer":
            return IntrinsicSizes(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        thickness = float(props["thickness"])
        width, height = ((0.0, thickness) if props["orientation"] == "horizontal"
                         else (thickness, 0.0))
        return IntrinsicSizes(
            width, width, height, height, width, height,
        )

    @staticmethod
    def _image_metrics(widget: object) -> IntrinsicSizes:
        from psx.renderers.components.image import compute_target_size
        source = getattr(widget, "_psx_image_cache", None)
        if source is None:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Tk Image source has no decodable intrinsic dimensions.",
            )
        if hasattr(source, "size"):
            sw, sh = source.size
        else:
            sw, sh = source.width(), source.height()
        props = widget._psx_props
        width, height = compute_target_size(sw, sh, props["width"], props["height"])
        return IntrinsicSizes(
            float(width), float(width), float(height), float(height),
            float(width), float(height),
        )

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
        # GUI toolkit imports remain lazy: the G1 Flex contract is backend-free.
        from tkinter import font as tkfont
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
            # Tcl returns an empty result when there are zero display-line
            # *transitions* (the single-line case), not an error.
            lines = (int(count[0]) if count else 0) + 1
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

    @staticmethod
    def _css_text_metrics(widget: object, width: float | None) -> IntrinsicSizes:
        """Measure the same native Tk Text wrapping rules used by CSS leading."""
        import tkinter as tk
        font = widget._psx_text_font
        text = str(widget.cget("text"))
        leading = float(widget._psx_css_line_height)
        natural = max((font.measure(line) for line in text.split("\n")), default=0)
        available = max(1, round(natural if width is None else width))
        probe = tk.Text(widget.master, font=font, wrap="word", borderwidth=0,
                        highlightthickness=0, padx=0, pady=0)
        try:
            probe.insert("1.0", text)
            probe.place(x=0, y=0, width=available, height=10000)
            probe.lower()
            probe.update_idletasks()
            count = probe.count("1.0", "end-1c", "displaylines")
            lines = max(1, (int(count[0]) if count else 0) + 1)
            height = float(lines) * leading
            measured_width = float(natural if width is None else min(natural, width))
            return IntrinsicSizes(measured_width, float(natural), height, height,
                                  measured_width, height)
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
        if request.node_id in self._spacer_ids:
            return MeasuredBox(
                request.node_id, self._structural_metrics("Spacer", {}),
                request.constraints, request.revision,
            )
        if request.node_id in self._divider_nodes:
            return MeasuredBox(
                request.node_id,
                self._structural_metrics("Divider", self._divider_nodes[request.node_id]),
                request.constraints, request.revision,
            )
        if request.node_id in self._image_ids:
            return MeasuredBox(
                request.node_id, self._image_metrics(widget),
                request.constraints, request.revision,
            )
        if getattr(widget, "_psx_css_line_height", None) is not None:
            metrics = self._css_text_metrics(widget, None)
            font = widget._psx_text_font
            font_height = float(font.metrics("linespace"))
            ascent = float(font.metrics("ascent"))
            offset = max(0.0, (metrics.preferred_height - font_height) / 2.0)
            metrics = replace(
                metrics, baseline=min(metrics.preferred_height, offset + ascent),
            )
            return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)
        if request.node_id in self._textarea_ids:
            metrics = self._textarea_metrics(widget, None)
            return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)
        # On later commits the Text widget may keep a wrapping constraint
        # from the previous SFLE allocation. Take intrinsic hints UNWRAPPED
        # so a previous narrow viewport cannot poison the new inline basis.
        wrap_key = "wraplength" in (widget.keys() if hasattr(widget, "keys") else ())
        old_wrap = widget.cget("wraplength") if wrap_key else None
        changed_wrap = wrap_key and str(old_wrap) not in ("0", "0.0")
        try:
            if changed_wrap:
                widget.configure(wraplength=0)
            # A changed native wrap constraint must settle before reading
            # geometry. Ordinary leaves keep the existing port contract and
            # require no Tk idle-drain method.
            if changed_wrap:
                widget.update_idletasks()
            width = float(widget.winfo_reqwidth())
            height = float(widget.winfo_reqheight())
        finally:
            if changed_wrap:
                widget.configure(wraplength=old_wrap)
        if width < 0 or height < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid Tk requested widget size.")
        font = getattr(widget, "_psx_text_font", None)
        ascent = float(font.metrics("ascent")) if font is not None else None
        metrics = IntrinsicSizes(
            min_content_width=width, max_content_width=width,
            min_content_height=height, max_content_height=height,
            preferred_width=width, preferred_height=height,
            baseline=min(height, ascent) if ascent is not None else None,
        )
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes:
        """Measure a Tk leaf after applying a temporary wrapping constraint."""
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Tk measurement requires its owning thread.")
        widget = self._widgets.get(node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Tk measurement node.", node_id)
        if getattr(widget, "_psx_css_line_height", None) is not None:
            return self._css_text_metrics(widget, width)
        if node_id in self._textarea_ids:
            return self._textarea_metrics(widget, width)
        previous = None
        changed_wrap = False
        try:
            keys = widget.keys() if hasattr(widget, "keys") else ()
            if "wraplength" in keys:
                previous = widget.cget("wraplength")
                requested = max(0, round(width))
                # A Grid transaction has already resolved natural Tk size
                # hints. If unwrapped text fits its assigned width, applying
                # wraplength only adds a global Tcl idle drain without changing
                # the intrinsic height. Do not speculate for pre-wrapped text.
                # Tcl/Tk's empty wraplength is the same unwrapped state as
                # zero. Do not force a global idle drain just to reassign a
                # wrap constraint when the native requested width already fits.
                if (self._idle_synced and str(previous) in ("", "0", "0.0")
                        and float(widget.winfo_reqwidth()) <= width):
                    natural_width = min(float(width), float(widget.winfo_reqwidth()))
                    natural_height = float(widget.winfo_reqheight())
                    return IntrinsicSizes(
                        natural_width, natural_width, natural_height,
                        natural_height, natural_width, natural_height,
                    )
                if previous != requested and str(previous) != str(requested):
                    widget.configure(wraplength=requested)
                    changed_wrap = True
            # A Grid transaction already drained the initial native queue.
            # Only changing wraplength makes that baseline obsolete; otherwise
            # reading the requested hints is safe without another global drain.
            if changed_wrap or not self._idle_synced:
                widget.update_idletasks()
            measured_width = min(float(width), float(widget.winfo_reqwidth()))
            height = float(widget.winfo_reqheight())
            return IntrinsicSizes(measured_width, measured_width, height, height,
                                  measured_width, height)
        finally:
            if changed_wrap:
                # Restoring the option does not need another synchronous Tk
                # idle drain: the just-read dimensions belong to the probe,
                # and a later measurement flushes before consulting hints.
                # This removes one global idle drain per wrapped Grid leaf.
                widget.configure(wraplength=previous)

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
