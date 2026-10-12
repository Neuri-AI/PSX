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
    ) -> None:
        self._widgets = dict(widgets)
        self._qtcore = qtcore
        if not textarea_ids <= self._widgets.keys():
            raise ValueError("TextArea measurement IDs must refer to mounted widgets.")
        self._textarea_ids = textarea_ids

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
        metrics = IntrinsicSizes(
            min_content_width=min_width, max_content_width=max(width, min_width),
            min_content_height=min_height, max_content_height=max(height, min_height),
            preferred_width=width, preferred_height=height,
        )
        # Qt sizeHint is NOT a proof of CSS min-content/max-content for wrapped
        # text. Consumers requiring exact intrinsic widths must supply richer
        # text metrics instead; this port only provides a native size hint.
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
