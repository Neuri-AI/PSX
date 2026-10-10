"""Kivy portable SpinBox with proportional controls and touch-friendly sizing."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.spinbox import (
    committed, formatted, normalized, spinbox_props, stepped, updated_spinbox_props,
)


class KivySpinBoxAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = spinbox_props(node.props)
        frame = BoxLayout(orientation="horizontal", spacing=0, size_hint=(None, None))
        minus = Button(text="−", size_hint=(None, None), width=48, height=48)
        entry = TextInput(
            multiline=False, halign="center", size_hint=(None, None),
            width=120, height=48, write_tab=False,
        )
        plus = Button(text="+", size_hint=(None, None), width=48, height=48)
        for child in (minus, entry, plus):
            frame.add_widget(child)
        frame.size = (216, 48)
        frame._psx_parts = (minus, entry, plus)
        frame._psx_props = props
        frame._psx_slot = None
        frame._psx_dirty = False
        frame._psx_updating = False
        frame._psx_entry_focus = False

        minus.bind(on_release=lambda *_: self._increment(frame, -1))
        plus.bind(on_release=lambda *_: self._increment(frame, 1))
        entry.bind(text=lambda *_: self._mark_dirty(frame))
        entry.bind(on_text_validate=lambda *_: self._commit(frame))
        entry.bind(focus=lambda _input, focused: self._on_focus(frame, focused))
        entry.bind(on_touch_down=lambda _, touch: False)
        self._apply(frame, props, sync_text=True)
        return KivyHandle("SpinBox", frame, props)

    @staticmethod
    def _mark_dirty(frame):
        if not frame._psx_updating:
            frame._psx_dirty = True

    def _on_focus(self, frame, focused):
        frame._psx_entry_focus = focused
        if not focused:
            self._commit(frame)

    def _emit(self, frame, value):
        props = frame._psx_props
        if value != normalized(props["value"], props) and frame._psx_slot is not None:
            frame._psx_slot.invoke(value)

    def _commit(self, frame):
        if not frame._psx_dirty:
            return
        frame._psx_dirty = False
        props = frame._psx_props
        entry = frame._psx_parts[1]
        value = committed(entry.text, props)
        frame._psx_updating = True
        try:
            entry.text = formatted(value, props)
        finally:
            frame._psx_updating = False
        self._emit(frame, value)

    def _increment(self, frame, direction):
        if not frame._psx_props["enabled"]:
            return
        self._commit(frame)
        props = frame._psx_props
        value = stepped(normalized(props["value"], props), direction, props)
        self._emit(frame, value)

    @staticmethod
    def _apply(frame, props, *, sync_text):
        frame._psx_props = props
        minus, entry, plus = frame._psx_parts
        value = normalized(props["value"], props)
        frame.disabled = not props["enabled"]
        minus.disabled = not props["enabled"] or value <= props["min"]
        plus.disabled = not props["enabled"] or value >= props["max"]
        if sync_text:
            frame._psx_updating = True
            try:
                entry.text = formatted(value, props)
                frame._psx_dirty = False
            finally:
                frame._psx_updating = False

    def update(self, renderer, handle, changed, removed):
        props = updated_spinbox_props(handle.props, changed, removed)
        self._apply(handle.widget, props, sync_text=True)
        handle.props = props

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
        if frame.parent is not None:
            frame.parent.remove_widget(frame)
