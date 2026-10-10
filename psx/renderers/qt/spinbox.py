"""Qt portable SpinBox with persistent - / entry / + controls."""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.spinbox import (
    committed, formatted, normalized, spinbox_props, stepped, updated_spinbox_props,
)


class QtSpinBoxAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = spinbox_props(node.props)
        core = importlib.import_module(f"{renderer._binding_package}.QtCore")
        widgets = renderer._widgets
        frame = widgets.QWidget()
        layout = widgets.QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        minus = widgets.QPushButton("−")
        plus = widgets.QPushButton("+")
        editor = widgets.QLineEdit()
        editor.setAlignment(getattr(getattr(core.Qt, "AlignmentFlag", core.Qt), "AlignCenter"))
        editor.setFixedWidth(94)
        minus.setFixedWidth(32)
        plus.setFixedWidth(32)
        frame._psx_parts = (minus, editor, plus)
        frame._psx_props = props
        frame._psx_slot = None
        frame._psx_dirty = False
        frame._psx_updating = False
        for item in frame._psx_parts:
            layout.addWidget(item)
        frame.setFixedWidth(158)
        # Keep the uniform control readable on all Qt bindings.
        frame.setStyleSheet(
            "QPushButton, QLineEdit { min-height: 28px; } "
            "QPushButton { padding: 0px; }"
        )
        minus.clicked.connect(lambda *_: self._increment(frame, -1))
        plus.clicked.connect(lambda *_: self._increment(frame, +1))
        editor.textEdited.connect(lambda *_: setattr(frame, "_psx_dirty", True))
        editor.returnPressed.connect(lambda: self._commit(frame))
        editor.installEventFilter(self._event_filter(frame, core))
        self._apply(frame, props, sync_text=True)
        return QtHandle("SpinBox", frame, props=props)

    def _event_filter(self, frame, core):
        qt = core.Qt
        keys = getattr(qt, "Key", qt)
        event_types = getattr(core.QEvent, "Type", core.QEvent)
        adapter = self

        class Filter(core.QObject):
            def eventFilter(self, obj, event):
                if event.type() == event_types.FocusOut:
                    adapter._commit(frame)
                if event.type() == event_types.KeyPress:
                    if event.key() == keys.Key_Up:
                        adapter._increment(frame, +1)
                        return True
                    if event.key() == keys.Key_Down:
                        adapter._increment(frame, -1)
                        return True
                if event.type() == event_types.Wheel and obj.hasFocus():
                    # Qt wheel angleDelta is expressed in units of eighth-degrees.
                    delta = event.angleDelta().y()
                    if delta:
                        adapter._increment(frame, 1 if delta > 0 else -1)
                        return True
            return False

        filter_object = Filter(frame)
        frame._psx_event_filter = filter_object
        return filter_object

    @staticmethod
    def _apply(frame, props, *, sync_text):
        frame._psx_props = props
        minus, editor, plus = frame._psx_parts
        frame.setEnabled(props["enabled"])
        current = normalized(props["value"], props)
        minus.setEnabled(props["enabled"] and current > props["min"])
        plus.setEnabled(props["enabled"] and current < props["max"])
        if sync_text:
            frame._psx_updating = True
            try:
                editor.setText(formatted(current, props))
                frame._psx_dirty = False
            finally:
                frame._psx_updating = False

    def _emit(self, frame, next_value):
        props = frame._psx_props
        if next_value != normalized(props["value"], props) and frame._psx_slot is not None:
            frame._psx_slot.invoke(next_value)

    def _commit(self, frame):
        if not frame._psx_dirty:
            return
        frame._psx_dirty = False
        editor = frame._psx_parts[1]
        props = frame._psx_props
        value = committed(editor.text(), props)
        editor.setText(formatted(value, props))
        self._emit(frame, value)

    def _increment(self, frame, direction):
        if not frame._psx_props["enabled"]:
            return
        props = frame._psx_props
        editor = frame._psx_parts[1]
        base = committed(editor.text(), props) if frame._psx_dirty else normalized(props["value"], props)
        frame._psx_dirty = False
        value = stepped(base, direction, props)
        self._emit(frame, value)

    def update(self, renderer, handle, changed, removed):
        props = updated_spinbox_props(handle.props, changed, removed)
        handle.props = props
        self._apply(handle.widget, props, sync_text=True)

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"SpinBox does not emit {event!r}.")
        handle.widget._psx_slot = slot
        return handle.widget, slot

    def unbind_event(self, renderer, subscription):
        frame, slot = subscription
        if frame._psx_slot is slot:
            frame._psx_slot = None

    def destroy(self, renderer, handle):
        frame = handle.widget
        frame._psx_slot = None
        frame._psx_parts[1].removeEventFilter(frame._psx_event_filter)
        frame.setParent(None)
        frame.deleteLater()
