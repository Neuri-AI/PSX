"""Qt intrinsic measurement port for the SFLE UI-thread protocol.

No Qt dependency is imported during module import. The caller supplies the
actual QWidget corresponding to each SFLE node ID. A Qt binding must match
the widget's own runtime; mixing bindings is unsupported.
"""
from __future__ import annotations

from collections.abc import Mapping

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


class QtMeasurementSource:
    """Wrap live Qt widget size hints without transferring them across threads."""

    def __init__(self, widgets: Mapping[str, object], *, qtcore: object) -> None:
        self._widgets = dict(widgets)
        self._qtcore = qtcore

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

    def port(self) -> NativeMeasurementPort:
        return NativeMeasurementPort(self.is_ui_thread, self.measure)
