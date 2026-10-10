"""Internal passthrough container adapter for the Tkinter renderer."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.errors import RendererCapabilityError


class TkBoxAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle
        master = parent.widget if parent is not None else renderer.root
        frame = ttk.Frame(master)
        return TkHandle("Box", frame, dict(node.props))

    def update(self, renderer, handle, changed, removed):
        if changed or removed:
            raise RendererCapabilityError(
                f"Box is an internal container and does not accept props: "
                f"{', '.join(sorted(set(changed) | removed))}"
            )

    def insert(self, renderer, parent, child, index):
        child.widget.pack(in_=parent.widget, fill=tk.BOTH, expand=True)
        return True

    def move(self, renderer, parent, child, index):
        return True

    def remove(self, renderer, parent, child):
        child.widget.pack_forget()
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Box does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()