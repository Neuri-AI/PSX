"""Built-in RadioGroup adapter for the Tkinter renderer.

ttk.Radiobutton uses a shared variable to know which one is selected. The
RadioGroup owns that variable and its trace callback; children are
configured with the shared variable and their own value on insert.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.contracts import RADIOGROUP_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.radio import (
    radiogroup_props,
    updated_radiogroup_props,
)


class TkRadioGroupAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle
        props = radiogroup_props({**RADIOGROUP_DEFAULTS, **node.props})

        master = parent.widget if parent is not None else renderer.root
        frame = ttk.Frame(master)
        frame._psx_radios = {}          # value -> ttk.Radiobutton
        frame._psx_event_slot = None
        frame._psx_updating = False
        # The variable type depends on the first Radio's value type. We use
        # a StringVar and stringify values on the way in/out; the portable
        # value is restored to str/int when dispatching on_change.
        frame._psx_var = tk.StringVar(master=frame)
        frame._psx_var.trace_add(
            "write",
            lambda *_: self._on_variable_changed(frame),
        )
        frame._psx_props = props
        return TkHandle("RadioGroup", frame, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_radiogroup_props(handle.props, changed, removed)
        handle.props = props
        frame = handle.widget
        frame._psx_props = props

        if "value" in changed or "value" in removed:
            self._sync_checked(frame, props["value"])

        # Repack to reflect spacing / padding / orientation changes.
        self._repack(frame)

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(
                f"RadioGroup does not emit {event!r}."
            )
        handle.widget._psx_event_slot = slot
        return None

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        if getattr(child, "node_type", None) != "Radio":
            raise RendererCapabilityError(
                "RadioGroup children must be Radio nodes."
            )
        frame = parent.widget
        value = child.props["value"]
        if value in frame._psx_radios:
            raise RendererCapabilityError(
                f"RadioGroup has duplicate Radio value {value!r}."
            )
        # Configure the ttk.Radiobutton to use the shared variable.
        radio_widget = child.widget
        radio_widget.configure(variable=frame._psx_var, value=str(value))
        frame._psx_radios[value] = radio_widget
        self._sync_checked(frame, parent.props["value"])
        self._repack(frame)
        return True

    def move(self, renderer, parent, child, index):
        self._repack(parent.widget)
        return True

    def remove(self, renderer, parent, child):
        frame = parent.widget
        value = child.props.get("value")
        if value is not None:
            frame._psx_radios.pop(value, None)
        child.widget.pack_forget()
        self._repack(frame)
        return True

    # -- helpers ----------------------------------------------------------

    def _on_variable_changed(self, frame):
        if frame._psx_updating:
            return
        slot = frame._psx_event_slot
        if slot is None:
            return
        raw = frame._psx_var.get()
        # Recover the original value type by looking it up in the registry.
        for value, radio in frame._psx_radios.items():
            if str(value) == raw:
                slot.invoke(value)
                return

    @staticmethod
    def _sync_checked(frame, selected_value):
        frame._psx_updating = True
        try:
            if selected_value is None:
                # tk has no "none selected" for StringVar; use an impossible
                # sentinel that no radio uses.
                frame._psx_var.set("")
            else:
                frame._psx_var.set(str(selected_value))
        finally:
            frame._psx_updating = False

    @staticmethod
    def _repack(frame):
        props = frame._psx_props
        orientation = props["orientation"]
        spacing = int(props["spacing"])
        padding = props["padding"]
        if isinstance(padding, int):
            pad = (padding, padding)
        elif len(padding) == 2:
            pad = tuple(padding)
        else:
            pad = (padding[0], padding[1])
        side = tk.TOP if orientation == "vertical" else tk.LEFT
        for index, (value, radio) in enumerate(frame._psx_radios.items()):
            radio.pack_forget()
            if orientation == "vertical":
                radio.pack(in_=frame, side=side, anchor=tk.W,
                           pady=(0, spacing) if index < len(frame._psx_radios) - 1 else 0,
                           padx=0)
            else:
                radio.pack(in_=frame, side=side, anchor=tk.W,
                           padx=(0, spacing) if index < len(frame._psx_radios) - 1 else 0,
                           pady=0)
        frame.configure(padding=pad)