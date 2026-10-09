"""Built-in Row adapter for the Tkinter renderer."""

import tkinter as tk
from tkinter import ttk

from psx.core.contracts import ROW_DEFAULTS, validate_row_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.row import child_align, child_expand, normalize_padding, updated_row_props


class TkRowAdapter:
    def create(self, renderer, node, parent):
        props = {**ROW_DEFAULTS, **node.props}
        validate_row_props(props)
        left, top, right, bottom = normalize_padding(props["padding"])
        frame = ttk.Frame(parent.widget if parent is not None else renderer.root,
                          padding=(left, top, right, bottom))
        frame.state(["!disabled" if props["enabled"] else "disabled"])
        from psx.renderers.tkinter.tkinter import TkHandle
        return TkHandle("Row", frame, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_row_props(handle.props, changed, removed)
        handle.props = props
        left, top, right, bottom = normalize_padding(props["padding"])
        handle.widget.configure(padding=(left, top, right, bottom))
        handle.widget.state(["!disabled" if props["enabled"] else "disabled"])
        self._repack(handle)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Row does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()

    def insert(self, renderer, parent, child, index):
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        self._repack(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.children.remove(child)
        parent.children.insert(index, child)
        self._repack(parent)
        return True

    def remove(self, renderer, parent, child):
        if child in parent.children:
            parent.children.remove(child)
        child.widget.pack_forget()
        self._repack(parent)
        return True

    def _repack(self, container):
        spacing = int(container.props.get("spacing", 0))
        for index, child in enumerate(container.children):
            child.widget.pack_forget()
            child.widget.pack(in_=container.widget, **self._pack_options(container, index, spacing))

    @staticmethod
    def _pack_options(container, index, spacing):
        child = container.children[index]
        align, expand = child_align(container.props, index), child_expand(container.props, index)

        # Un Spacer absorbe todo el sobrante horizontal del Row. En Tk eso
        # requiere fill=BOTH para ocupar el área asignada y expand=True para
        # que pack le dé el espacio libre.
        if child.node_type == "Spacer":
            return {"side": tk.LEFT, "fill": tk.BOTH, "expand": True, "anchor": tk.CENTER,
                    "padx": (0, 0) if index == 0 else (spacing, 0), "pady": 0}

        fill_y = align == "stretch"
        fill = tk.BOTH if fill_y and expand else tk.Y if fill_y else tk.X if expand else tk.NONE
        anchor = tk.CENTER if fill_y else {"start": tk.N, "center": tk.CENTER, "end": tk.S}[align]
        return {"side": tk.LEFT, "fill": fill, "expand": bool(expand), "anchor": anchor,
                "padx": (0, 0) if index == 0 else (spacing, 0), "pady": 0}