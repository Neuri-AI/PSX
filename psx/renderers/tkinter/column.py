"""Built-in Column adapter for the Tkinter renderer.

This is where the Tk-specific hacks live: spacing is emulated by stacking
``pady`` between siblings; align/expand are packed per-child.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.contracts import COLUMN_DEFAULTS, validate_column_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.column import (
    child_align,
    child_expand,
    normalize_padding,
    updated_column_props,
)


class TkColumnAdapter:
    def create(self, renderer, node, parent):
        master = parent.widget if parent is not None else renderer.root
        props = {**COLUMN_DEFAULTS, **node.props}
        validate_column_props(props)
        l, t, r, b = normalize_padding(props["padding"])
        frame = ttk.Frame(master, padding=(l, t, r, b))
        self._apply_enabled(frame, props["enabled"])
        from psx.renderers.tkinter.tkinter import TkHandle
        return TkHandle("Column", frame, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_column_props(handle.props, changed, removed)
        handle.props = props
        l, t, r, b = normalize_padding(props["padding"])
        handle.widget.configure(padding=(l, t, r, b))
        self._apply_enabled(handle.widget, props["enabled"])
        self._repack(handle)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Column does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()

    # -- hooks ------------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        container = parent
        if child in container.children:
            container.children.remove(child)
        container.children.insert(index, child)
        self._repack(container)
        return True

    def move(self, renderer, parent, child, index):
        container = parent
        container.children.remove(child)
        container.children.insert(index, child)
        self._repack(container)
        return True

    def remove(self, renderer, parent, child):
        container = parent
        if child in container.children:
            container.children.remove(child)
        child.widget.pack_forget()
        self._repack(container)
        return True

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _apply_enabled(frame, enabled):
        """Set the ttk container state; child widgets retain their own state."""
        frame.state(["!disabled" if enabled else "disabled"])

    def _repack(self, container):
        frame = container.widget
        spacing = int(container.props.get("spacing", 0))
        for index, child in enumerate(container.children):
            child.widget.pack_forget()
            child.widget.pack(in_=frame, **self._pack_options(container, index, spacing))

    @staticmethod
    def _pack_options(container, index, spacing):
        align = child_align(container.props, index)
        expand = child_expand(container.props, index)

        if align == "stretch":
            fill_x = True
            anchor = tk.CENTER
        else:
            fill_x = False
            anchor = {"start": tk.W, "center": tk.CENTER, "end": tk.E}[align]

        if fill_x and expand:
            fill = tk.BOTH
        elif fill_x:
            fill = tk.X
        elif expand:
            fill = tk.Y
        else:
            fill = tk.NONE

        return {
            "side": tk.TOP,
            "fill": fill,
            "expand": bool(expand),
            "anchor": anchor,
            "pady": (0, 0) if index == 0 else (spacing, 0),
        }
