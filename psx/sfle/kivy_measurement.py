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
        image_ids: frozenset[str] = frozenset(),
        spacer_ids: frozenset[str] = frozenset(),
        divider_nodes: Mapping[str, object] | None = None,
    ) -> None:
        self._widgets = dict(widgets)
        if not textarea_ids <= self._widgets.keys():

            raise ValueError(
                "TextArea measurement IDs must map to mounted Kivy controls.")

        self._textarea_ids = textarea_ids
        if not image_ids <= self._widgets.keys():

            raise ValueError(
                "Image measurement IDs must refer to mounted Kivy controls.")

        self._image_ids = image_ids
        if not spacer_ids <= self._widgets.keys():

            raise ValueError(
                "Spacer measurement IDs must refer to native widgets.")

        self._spacer_ids = spacer_ids
        self._divider_nodes = dict(divider_nodes or {})
        if not self._divider_nodes.keys() <= self._widgets.keys():
            raise ValueError("Divider IDs must refer to native widgets.")
        self._owner_thread = threading.get_ident()

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
        texture = widget.texture
        if texture is None:
            # kivy.uix.image.Image normally loads local sources immediately.
            # On providers deferring the widget texture, force a synchronous
            # *source* decode, never fall back to Widget.size=(100,100).
            from kivy.core.image import Image as CoreImage
            try:
                texture = CoreImage(widget.source).texture
            except Exception as exc:
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                    "Kivy Image source cannot be synchronously decoded.",
                ) from exc
        if texture is None:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Kivy Image texture has no intrinsic dimensions.",
            )
        props = widget._psx_props
        sw, sh = texture.size

        width, height = compute_target_size(
            sw, sh, props["width"], props["height"])

        return IntrinsicSizes(
            float(width), float(width), float(height), float(height),
            float(width), float(height),
        )

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
        # Synchronize native font options and wrapped lines before measurement.
        probe._refresh_line_options()
        height = float(probe.minimum_height)
        natural = max(
            (float(label.width) for label in probe._lines_labels),
            default=0.0,
        ) + float(probe.padding[0]) + float(probe.padding[2])
        if not math.isfinite(height) or not math.isfinite(natural):

            raise SFLEError(

                DiagnosticCode.UNSUPPORTED_MEASUREMENT,

                "Kivy TextArea returned nonfinite intrinsic metrics.",

            )

        return IntrinsicSizes(natural, natural, height, height, natural, height)

    @staticmethod
    def _control_metrics(widget: object, kind: str) -> IntrinsicSizes:
        """Get native glyph and theme metrics, never an assigned Widget.size.

        Kivy Checkbox and ProgressBar have graphical skins without a CSS
        intrinsic-width API. Their portable auto preference uses density-
        scaled design minima; Checkbox's theme art is measured if available.
        Input is measured from native CoreLabel glyph textures and padding.
        """
        from kivy.metrics import dp

        def density_pixels(logical_pixels: float) -> float:
            """Return a usable density-scaled design minimum.

            A partially initialized Kivy metrics provider can report NaN on
            Windows.  These values are portable design minima, so retain the
            logical-pixel minimum until the provider has a finite density.
            """
            scaled = float(dp(logical_pixels))
            return scaled if math.isfinite(scaled) and scaled > 0 else logical_pixels

        if kind == "Input":
            from kivy.core.text import Label as CoreLabel
            candidates = (widget.text or "", widget.hint_text or "", "M")
            text_width = 0.0
            line_height = 0.0
            for text in candidates:
                label = CoreLabel(text=text, font_name=widget.font_name,
                                  font_size=widget.font_size)
                label.refresh()
                text_width = max(text_width, float(label.texture.size[0]))
                line_height = max(line_height, float(label.texture.size[1]))
            left, top, right, bottom = [float(v) for v in widget.padding]

            width = max(density_pixels(72), text_width +
                        left + right + density_pixels(12))

            height = max(density_pixels(32), line_height + top + bottom)
        elif kind == "Checkbox":
            # Graphic artwork is the closest native intrinsic hint.
            # For themes that do not expose an image, adopt the platform's
            # explicit density-scaled minimum interactive target.
            from kivy.core.image import Image as CoreImage
            sizes = []
            for attribute in ("background_checkbox_normal", "background_checkbox_down"):
                uri = getattr(widget, attribute, None)
                if uri:
                    try:
                        texture = CoreImage(uri).texture
                        if texture is not None:
                            sizes.append(tuple(float(x) for x in texture.size))
                    except (OSError, ValueError):
                        pass
            width = max([density_pixels(32)] + [x for x, _ in sizes])
            height = max([density_pixels(32)] + [y for _, y in sizes])
            caption = getattr(widget, "_psx_label", None)
            if caption is not None and caption.text:
                caption.texture_update()
                width += max(0.0, float(caption.texture_size[0])) + density_pixels(8)
                height = max(height, float(caption.texture_size[1]))
        elif kind == "ProgressBar":
            # No content/text and no theme intrinsic-size interface in
            # Kivy ProgressBar: use a named portable design minimum instead
            # of the mutable default Widget.size (100, 100).
            width, height = density_pixels(120), density_pixels(20)
        else:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            f"Unrecognized native control {kind!r}.")
        if not math.isfinite(width) or not math.isfinite(height) or min(width, height) <= 0:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Non-finite Kivy control intrinsic size.")
        return IntrinsicSizes(width, width, height, height, width, height)

    def is_ui_thread(self) -> bool:
        return threading.get_ident() == self._owner_thread

    def measure(self, request: MeasurementRequest) -> MeasuredBox:
        if not isinstance(request, MeasurementRequest):
            raise TypeError("Expected MeasurementRequest.")
        if not self.is_ui_thread():

            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Kivy measurement requires UI thread.")

        widget = self._widgets.get(request.node_id)
        if widget is None:

            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Unknown Kivy measurement node.")

        if request.node_id in self._spacer_ids:
            return MeasuredBox(
                request.node_id, self._structural_metrics("Spacer", {}),
                request.constraints, request.revision,
            )
        if request.node_id in self._divider_nodes:
            return MeasuredBox(
                request.node_id,

                self._structural_metrics(
                    "Divider", self._divider_nodes[request.node_id]),

                request.constraints, request.revision,
            )
        if request.node_id in self._image_ids:
            return MeasuredBox(
                request.node_id, self._image_metrics(widget),
                request.constraints, request.revision,
            )
        if request.node_id in self._textarea_ids:
            metrics = self._textarea_metrics(widget, None)
            return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)
        control_kind = getattr(widget, "_psx_sfle_intrinsic_kind", None)
        if control_kind is not None:
            return MeasuredBox(
                request.node_id, self._control_metrics(widget, control_kind),
                request.constraints, request.revision,
            )
        if getattr(widget, "_psx_sfle_badge", False):
            width, height = widget._psx_natural_size

            metrics = IntrinsicSizes(
                width, width, height, height, width, height)

            return MeasuredBox(
                request.node_id, metrics, request.constraints, request.revision,
            )
        if getattr(widget, "_psx_sfle_link", False):
            width = max(1.0, float(widget.texture_size[0]) + 4.0)
            height = max(24.0, float(widget.texture_size[1]) + 4.0)

            metrics = IntrinsicSizes(
                width, width, height, height, width, height)

            return MeasuredBox(
                request.node_id, metrics, request.constraints, request.revision,
            )
        # Internal chrome is positioned by native children; SFLE owns only
        # the composite host's outer rect. Never read its previous allocation
        # as an intrinsic sizing suggestion.
        if getattr(widget, "_psx_sfle_switch", False) or getattr(
            widget, "_psx_sfle_spinbox", False
        ):
            width, height = widget._psx_intrinsic_size
            metrics = IntrinsicSizes(
                width, width, height, height, width, height)

            return MeasuredBox(
                request.node_id, metrics, request.constraints, request.revision,
            )
        if getattr(widget, "_psx_sfle_radio", False):
            width, height = widget._psx_intrinsic_radio
            metrics = IntrinsicSizes(
                width, width, height, height, width, height)
            return MeasuredBox(
                request.node_id, metrics, request.constraints, request.revision,
            )
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

            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Invalid Kivy intrinsic metrics.")

        # Kivy's Label texture height is the native line box in device
        # pixels. Its public SDL2 provider does not expose a separate font
        # ascent. Use the measured line-box end consistently for all Text
        # siblings (including those nested in spans); shared alignment then
        # cancels the added span padding without guessing a pixel offset.
        is_text = hasattr(widget, "text") and hasattr(widget, "font_size")
        metrics = IntrinsicSizes(
            width, width, height, height, width, height,
            baseline=height if is_text else None,
        )
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def measure_width(self, node_id: str, width: float | None) -> IntrinsicSizes:
        """Measure a Kivy leaf at the exact post-flex content width."""
        if not self.is_ui_thread():

            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Kivy measurement requires UI thread.")

        widget = self._widgets.get(node_id)
        if widget is None:

            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Unknown Kivy measurement node.", node_id)

        if node_id in self._textarea_ids:
            return self._textarea_metrics(widget, width)
        control_kind = getattr(widget, "_psx_sfle_intrinsic_kind", None)
        if control_kind in ("Input", "Checkbox", "ProgressBar"):
            # Single-line native controls do not reflow text into a taller
            # control. Their intrinsic height is stable at an assigned width.
            return self._control_metrics(widget, control_kind)
        previous = getattr(widget, "text_size", None)
        changed = hasattr(widget, "text_size")
        try:
            if changed:
                widget.text_size = ((float(width), None) if width is not None
                                    else (None, None))
            refresh = getattr(widget, "texture_update", None)
            if callable(refresh):
                refresh()
            pair = (widget.texture_size if hasattr(widget, "texture_size")
                    else widget.minimum_size if hasattr(widget, "minimum_size") else None)
            if pair is None:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Kivy widget has no width-dependent intrinsic measurement.", node_id)
            measured_width, height = (float(value) for value in pair)
            if width is not None:
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
