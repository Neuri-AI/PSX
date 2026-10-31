"""Qt intrinsic measurement port for the SFLE UI-thread protocol.

No Qt dependency is imported during module import. The caller supplies the
actual QWidget corresponding to each SFLE node ID. A Qt binding must match
the widget's own runtime; mixing bindings is unsupported.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from importlib import import_module
import math

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class QtMeasurementSource:
    """Wrap live Qt widget size hints without transferring them across threads."""

    def __init__(
        self, widgets: Mapping[str, object], *, qtcore: object,
        textarea_ids: frozenset[str] = frozenset(),
        text_ids: frozenset[str] = frozenset(),
        image_ids: frozenset[str] = frozenset(),
        spacer_ids: frozenset[str] = frozenset(),
        divider_nodes: Mapping[str, object] | None = None,
    ) -> None:
        self._widgets = dict(widgets)
        self._qtcore = qtcore
        if not textarea_ids <= self._widgets.keys():
            raise ValueError("TextArea measurement IDs must refer to mounted widgets.")
        self._textarea_ids = textarea_ids
        if not text_ids <= self._widgets.keys():
            raise ValueError("Text measurement IDs must refer to mounted Qt widgets.")
        self._text_ids = text_ids
        if not image_ids <= self._widgets.keys():
            raise ValueError("Image measurement IDs must refer to mounted Qt widgets.")
        self._image_ids = image_ids
        if not spacer_ids <= self._widgets.keys():
            raise ValueError("Spacer measurement IDs must refer to native widgets.")
        self._spacer_ids = spacer_ids
        self._divider_nodes = dict(divider_nodes or {})
        if not self._divider_nodes.keys() <= self._widgets.keys():
            raise ValueError("Divider IDs must refer to native widgets.")

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
        pixmap = getattr(widget, "_psx_pixmap_cache", None)
        if pixmap is None or pixmap.isNull():
            # An unresolved local resource has no intrinsic image dimensions.
            # Measure the accessible alt-text placeholder instead of aborting
            # the entire Cinnamon render; hot reload may supply the file later.
            props = widget._psx_props
            hint = widget.sizeHint()
            width = float(props["width"] or max(1, hint.width()))
            height = float(props["height"] or max(1, hint.height()))
            return IntrinsicSizes(width, width, height, height, width, height)
        props = widget._psx_props
        width, height = compute_target_size(
            pixmap.width(), pixmap.height(), props["width"], props["height"],
        )
        return IntrinsicSizes(
            float(width), float(width), float(height), float(height),
            float(width), float(height),
        )

    @staticmethod
    def _text_intrinsic_widths(widget: object, fallback_min: float) -> tuple[float, float]:
        """Measure real min/max-content, not QLabel's word-wrapped sizeHint.

        QLabel's sizeHint() with wordWrap=True deliberately proposes a
        relatively narrow multi-line width. CSS flex items with align-items:
        center need their *max-content* contribution for auto cross sizing.
        Height remains width-dependent and is measured separately by Qt.
        """
        # QTextDocument.setTextWidth() is changed by heightForWidth() and
        # paintEvent(). Therefore QWidget.sizeHint() on the CSS line-height
        # label can reflect the *previously wrapped width*, not max-content.
        # Measure the unwrapped string against the widget's current font in
        # both CSS and plain QLabel paths. Fixed CSS line-height affects only
        # height, never the advance of glyphs in the inline axis.
        metrics = widget.fontMetrics()
        text = widget.text()
        lines = text.split("\n") if text else [""]
        edges = (max(0, int(widget.margin())) * 2
                 + max(0, int(widget.frameWidth())) * 2)
        natural = float(max(metrics.horizontalAdvance(line) for line in lines) + edges)
        # Ignore artificial preferred widths caused by wrapping; preserve
        # the actual unwrapped content width as the max-content bound.
        natural = max(0.0, natural)
        minimum = min(natural, fallback_min)
        return minimum, natural

    def is_ui_thread(self) -> bool:
        qthread = getattr(self._qtcore, "QThread", None)
        if qthread is None or not callable(getattr(qthread, "currentThread", None)):
            return False
        thread = qthread.currentThread()
        return all(callable(getattr(widget, "thread", None))
                   and widget.thread() == thread for widget in self._widgets.values())

    def measure(self, request: MeasurementRequest) -> MeasuredBox:
        if not isinstance(request, MeasurementRequest):
            raise TypeError("Expected MeasurementRequest.")
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Qt measurement requires widget UI thread.")
        widget = self._widgets.get(request.node_id)
        if widget is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Qt measurement node.")
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
        hint = widget.sizeHint()
        minimum = widget.minimumSizeHint()
        if not hint.isValid():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Qt widget has no valid intrinsic size hint.")
        width = max(0.0, float(hint.width()))
        height = max(0.0, float(hint.height()))
        min_width = max(0.0, float(minimum.width())) if minimum.isValid() else 0.0
        min_height = max(0.0, float(minimum.height())) if minimum.isValid() else 0.0
        axis = request.constraints.width
        # Qt's heightForWidth() is meaningful only for widgets reporting it.
        if axis.definite and widget.hasHeightForWidth():
            assert axis.value is not None
            derived = widget.heightForWidth(round(axis.value))
            if derived < 0:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Qt heightForWidth returned invalid size.")
            height = float(derived)
        # Inline form controls participate in their text baseline, not their
        # bottom widget edge. Qt sizeHint alone does not provide a baseline.
        baseline = None
        if callable(getattr(widget, "inherits", None)) and any(
            widget.inherits(name) for name in ("QLineEdit", "QPushButton")
        ):
            font_metrics = widget.fontMetrics()
            baseline = min(height, max(0.0,
                (height - float(font_metrics.height())) / 2.0
                + float(font_metrics.ascent())))
        if request.node_id in self._text_ids:
            min_width, width = self._text_intrinsic_widths(widget, min_width)
        metrics = IntrinsicSizes(
            min_content_width=min_width, max_content_width=max(width, min_width),
            min_content_height=min_height, max_content_height=max(height, min_height),
            preferred_width=width, preferred_height=height, baseline=baseline,
        )
        # Native text max-content is measured unwrapped, not from Qt's
        # wrapped sizeHint; used height still follows heightForWidth().
        return MeasuredBox(request.node_id, metrics, request.constraints, request.revision)

    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes:
        """Remeasure wrapped native content at the *actual* SFLE leaf width.

        QLabel exposes heightForWidth. QPlainTextEdit does not: its default
        sizeHint is a scrolling viewport, not the height of its text. For a
        TextArea with CSS auto-height, measure a detached QTextDocument using
        its current text/font, leaving the live edit's cursor, focus, signals,
        scrolling and document completely untouched.
        """
        from .model import AvailableSize, LayoutConstraints
        if not isinstance(width, (int, float)) or isinstance(width, bool) or (
            not math.isfinite(width) or width < 0
        ):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt width-dependent measurement requires a finite nonnegative width.")
        baseline = self.measure(MeasurementRequest(
            node_id,
            LayoutConstraints(AvailableSize(width, True), AvailableSize(None, False)),
            0, 0,
        )).intrinsic
        if node_id not in self._textarea_ids:
            return baseline
        widget = self._widgets[node_id]
        gui = import_module(self._qtcore.__name__.rsplit(".", 1)[0] + ".QtGui")
        document = gui.QTextDocument()
        document.setDefaultFont(widget.font())
        document.setDocumentMargin(widget.document().documentMargin())
        option = widget.document().defaultTextOption()
        wrap = getattr(gui.QTextOption, "WrapMode", gui.QTextOption)
        edit_wrap = getattr(type(widget), "LineWrapMode", type(widget))
        if widget.lineWrapMode() == edit_wrap.NoWrap:
            option.setWrapMode(wrap.NoWrap)
        else:
            option.setWrapMode(wrap.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        document.setPlainText(widget.toPlainText())
        frame = max(0, widget.frameWidth())
        document.setTextWidth(max(1.0, float(width) - 2.0 * frame))
        measured_height = float(document.size().height()) + 2.0 * frame
        if not math.isfinite(measured_height) or measured_height < 0:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt TextArea returned invalid wrapped document height.")
        height = float(math.ceil(measured_height))
        return replace(
            baseline, min_content_height=height,
            max_content_height=height, preferred_height=height,
        )

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
