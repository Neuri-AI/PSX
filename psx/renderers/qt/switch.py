"""Animated native-painted Switch for all supported Qt bindings."""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.switch import SWITCH_SIZES, switch_props, updated_switch_props


def _switch_widget_class(binding: str):
    core = importlib.import_module(f"{binding}.QtCore")
    gui = importlib.import_module(f"{binding}.QtGui")
    widgets = importlib.import_module(f"{binding}.QtWidgets")
    Qt = core.Qt
    property_type = getattr(core, "Property", None) or core.pyqtProperty
    key_space = getattr(getattr(Qt, "Key", Qt), "Key_Space")
    key_return = getattr(getattr(Qt, "Key", Qt), "Key_Return")
    key_enter = getattr(getattr(Qt, "Key", Qt), "Key_Enter")
    focus_policy = getattr(getattr(Qt, "FocusPolicy", Qt), "StrongFocus")
    pen_style = getattr(getattr(Qt, "PenStyle", Qt), "NoPen")
    align = getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignVCenter") | getattr(
        getattr(Qt, "AlignmentFlag", Qt), "AlignLeft"
    )

    class AnimatedSwitch(widgets.QAbstractButton):
        def __init__(self):
            super().__init__()
            self.setCheckable(True)
            self.setFocusPolicy(focus_policy)
            self._progress = 0.0
            self._label = ""
            self._size_name = "medium"
            self._animation = core.QPropertyAnimation(self, b"progress", self)
            self._animation.setDuration(160)
            easing = getattr(getattr(core.QEasingCurve, "Type", core.QEasingCurve), "OutCubic")
            self._animation.setEasingCurve(easing)
            self.clicked.connect(self._animate_click)
            self._sync_dimensions()

        def _get_progress(self):
            return self._progress

        def _set_progress(self, value):
            self._progress = float(value)
            self.update()

        progress = property_type(float, _get_progress, _set_progress)

        def _sync_dimensions(self):
            width, height = SWITCH_SIZES[self._size_name]
            metrics = self.fontMetrics()
            label_width = metrics.horizontalAdvance(self._label) if self._label else 0
            self.setFixedSize(width + (10 + label_width if self._label else 0), max(height, metrics.height() + 4))
            self.setAccessibleName(self._label)

        def _animate_click(self, *_):
            self.animate_to(self.isChecked())

        def animate_to(self, checked: bool):
            self._animation.stop()
            self._animation.setStartValue(self._progress)
            self._animation.setEndValue(1.0 if checked else 0.0)
            self._animation.start()

        def set_props(self, props):
            self._label = props["label"]
            self._size_name = props["size"]
            self._sync_dimensions()
            self.setEnabled(props["enabled"])
            if self.isChecked() != props["checked"]:
                blocked = self.blockSignals(True)
                try:
                    self.setChecked(props["checked"])
                finally:
                    self.blockSignals(blocked)
                self.animate_to(props["checked"])

        def paintEvent(self, event):
            width, height = SWITCH_SIZES[self._size_name]
            y = (self.height() - height) / 2
            painter = gui.QPainter(self)
            painter.setRenderHint(gui.QPainter.RenderHint.Antialiasing if hasattr(gui.QPainter, "RenderHint") else gui.QPainter.Antialiasing)
            painter.setPen(pen_style)
            if not self.isEnabled():
                off, on = gui.QColor("#BBBBBB"), gui.QColor("#91B7A1")
            else:
                off, on = gui.QColor("#9CA3AF"), gui.QColor("#16A34A")
            t = self._progress
            color = gui.QColor(
                round(off.red() * (1-t) + on.red() * t),
                round(off.green() * (1-t) + on.green() * t),
                round(off.blue() * (1-t) + on.blue() * t),
            )
            painter.setBrush(color)
            painter.drawRoundedRect(core.QRectF(0, y, width, height), height / 2, height / 2)
            diameter = height - 6
            painter.setBrush(gui.QColor("white"))
            painter.drawEllipse(core.QRectF(3 + (width - height) * t, y + 3, diameter, diameter))
            if self._label:
                painter.setPen(self.palette().color(self.foregroundRole()))
                painter.drawText(core.QRectF(width + 10, 0, self.width() - width - 10, self.height()), align, self._label)
            painter.end()

        def keyPressEvent(self, event):
            if event.key() in (key_space, key_return, key_enter):
                # QAbstractButton implements Space; manually support Enter.
                if event.key() != key_space:
                    self.click()
                    event.accept()
                    return
            super().keyPressEvent(event)

        def stop(self):
            self._animation.stop()
            self.clicked.disconnect(self._animate_click)

    return AnimatedSwitch


class QtSwitchAdapter:
    def __init__(self):
        self._classes = {}

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = switch_props(node.props)
        binding = renderer._binding_package
        cls = self._classes.get(binding)
        if cls is None:
            cls = self._classes[binding] = _switch_widget_class(binding)
        widget = cls()
        widget.set_props(props)
        widget._progress = float(props["checked"])
        return QtHandle("Switch", widget, props=props)

    def update(self, renderer, handle, changed, removed):
        props = updated_switch_props(handle.props, changed, removed)
        handle.widget.set_props(props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"Switch does not emit {event!r}.")
        widget = handle.widget
        callback = lambda checked: slot.invoke(bool(checked))
        widget.clicked.connect(callback)
        return widget.clicked, callback

    def unbind_event(self, renderer, subscription):
        signal, callback = subscription
        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            pass

    def destroy(self, renderer, handle):
        widget = handle.widget
        widget.stop()
        widget.setParent(None)
        widget.deleteLater()
