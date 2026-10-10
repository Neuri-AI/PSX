"""Tkinter Select adapter: ttk.Combobox requires virtual-event binding.

The generic Tk primitive registry only handles configurable callback options;
<<ComboboxSelected>> needs bind/unbind, so this leaf uses a small adapter.
"""

from __future__ import annotations

from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.select import (
    select_items, select_props, updated_select_props,
)


class TkSelectAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = select_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        widget = ttk.Combobox(master, state="readonly")
        widget._psx_updating = False
        widget._psx_items = ()
        self._apply(widget, props)
        return TkHandle("Select", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_select_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"Select does not emit {event!r}.")
        widget = handle.widget

        def callback(_event):
            if widget._psx_updating:
                return
            index = widget.current()
            if index <= 0:
                return
            items = widget._psx_items
            if index - 1 < len(items):
                slot.invoke(items[index - 1][1])

        binding_id = widget.bind("<<ComboboxSelected>>", callback, add="+")
        return widget, binding_id

    def unbind_event(self, renderer, subscription):
        widget, binding_id = subscription
        if widget.winfo_exists() and binding_id:
            widget.unbind("<<ComboboxSelected>>", binding_id)

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()

    @staticmethod
    def _apply(widget, props):
        items = select_items(props)
        widget._psx_updating = True
        try:
            widget._psx_items = items
            widget.configure(
                values=(props["placeholder"], *(label for label, _ in items)),
                state="readonly" if props["enabled"] else "disabled",
            )
            selected = 0
            for index, (_label, value) in enumerate(items, start=1):
                if type(value) is type(props["value"]) and value == props["value"]:
                    selected = index
                    break
            widget.current(selected)
        finally:
            widget._psx_updating = False
