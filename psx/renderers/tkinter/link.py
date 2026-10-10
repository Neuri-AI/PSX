"""Portable Tk Link adapter with focus, mouse and keyboard activation."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.link import activate_link, link_props, updated_link_props


class TkLinkAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = link_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        widget = tk.Label(master, anchor="w", takefocus=True, bd=0)
        widget._psx_link_props = props
        widget._psx_link_slot = None
        widget._psx_font = tkfont.Font(widget, font=widget.cget("font"))
        for sequence in ("<ButtonRelease-1>", "<Return>", "<space>"):
            widget.bind(sequence, lambda _event, w=widget: self._activate(w))
        self._apply(widget, props)
        return TkHandle("Link", widget, props)

    @staticmethod
    def _activate(widget):
        props = widget._psx_link_props
        if not props["enabled"]:
            return "break"
        if props["href"] is not None:
            activate_link(props)
        else:
            slot = widget._psx_link_slot
            if slot is not None:
                slot.invoke()
        return "break"

    @staticmethod
    def _apply(widget, props):
        widget._psx_link_props = props
        widget._psx_font.configure(underline=props["underline"])
        widget.configure(
            text=props["label"],
            font=widget._psx_font,
            foreground=(props["color"] or "#2563EB") if props["enabled"] else "#808080",
            cursor="hand2" if props["enabled"] else "arrow",
        )

    def update(self, renderer, handle, changed, removed):
        props = updated_link_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_click":
            raise RendererCapabilityError(f"Link does not emit {event!r}.")
        handle.widget._psx_link_slot = slot
        return handle.widget, slot

    def unbind_event(self, renderer, subscription):
        widget, slot = subscription
        if widget._psx_link_slot is slot:
            widget._psx_link_slot = None

    def destroy(self, renderer, handle):
        widget = handle.widget
        widget._psx_link_slot = None
        if widget.winfo_exists():
            widget.destroy()
