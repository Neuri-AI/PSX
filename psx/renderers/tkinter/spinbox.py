"""Tkinter portable SpinBox with typed-entry commit and focus-aware wheel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.spinbox import (
    committed, formatted, normalized, spinbox_props, stepped, updated_spinbox_props,
)


class TkSpinBoxAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = spinbox_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        frame = ttk.Frame(master)
        minus = ttk.Button(frame, text="−", width=3)
        entry = ttk.Entry(frame, width=10, justify="center")
        plus = ttk.Button(frame, text="+", width=3)
        minus.pack(side="left")
        entry.pack(side="left")
        plus.pack(side="left")
        frame._psx_parts = (minus, entry, plus)
        frame._psx_props = props
        frame._psx_slot = None
        frame._psx_dirty = False
        frame._psx_updating = False
        frame._psx_var = tk.StringVar(master=frame)
        entry.configure(textvariable=frame._psx_var)
        frame._psx_trace = frame._psx_var.trace_add(
            "write", lambda *_: self._mark_dirty(frame)
        )
        minus.configure(command=lambda: self._increment(frame, -1))
        plus.configure(command=lambda: self._increment(frame, 1))
        entry.bind("<Return>", lambda event: self._commit(frame))
        entry.bind("<FocusOut>", lambda event: self._commit(frame))
        entry.bind("<Up>", lambda event: self._key_step(frame, 1))
        entry.bind("<Down>", lambda event: self._key_step(frame, -1))
        entry.bind("<MouseWheel>", lambda event: self._wheel(frame, event.delta))
        entry.bind("<Button-4>", lambda event: self._wheel(frame, 1))
        entry.bind("<Button-5>", lambda event: self._wheel(frame, -1))
        self._apply(frame, props, sync_text=True)
        return TkHandle("SpinBox", frame, props)

    @staticmethod
    def _mark_dirty(frame):
        if not frame._psx_updating:
            frame._psx_dirty = True

    def _emit(self, frame, value):
        props = frame._psx_props
        if value != normalized(props["value"], props) and frame._psx_slot is not None:
            frame._psx_slot.invoke(value)

    def _commit(self, frame):
        if not frame._psx_dirty:
            return "break"
        frame._psx_dirty = False
        props = frame._psx_props
        value = committed(frame._psx_var.get(), props)
        frame._psx_updating = True
        try:
            frame._psx_var.set(formatted(value, props))
        finally:
            frame._psx_updating = False
        self._emit(frame, value)
        return "break"

    def _increment(self, frame, direction):
        if not frame._psx_props["enabled"]:
            return
        self._commit(frame)
        props = frame._psx_props
        value = stepped(normalized(props["value"], props), direction, props)
        self._emit(frame, value)

    def _key_step(self, frame, direction):
        self._increment(frame, direction)
        return "break"

    def _wheel(self, frame, delta):
        if frame._psx_parts[1].focus_get() is frame._psx_parts[1] and delta:
            self._increment(frame, 1 if delta > 0 else -1)
        return "break"

    @staticmethod
    def _apply(frame, props, *, sync_text):
        frame._psx_props = props
        minus, entry, plus = frame._psx_parts
        current = normalized(props["value"], props)
        minus.state(("!disabled",) if props["enabled"] and current > props["min"] else ("disabled",))
        plus.state(("!disabled",) if props["enabled"] and current < props["max"] else ("disabled",))
        entry.state(("!disabled",) if props["enabled"] else ("disabled",))
        if sync_text:
            frame._psx_updating = True
            try:
                frame._psx_var.set(formatted(current, props))
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
        if frame.winfo_exists():
            frame._psx_var.trace_remove("write", frame._psx_trace)
            frame.destroy()
