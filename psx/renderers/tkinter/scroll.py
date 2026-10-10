"""Tkinter Scroll with Canvas viewport, native child frame and overlay thumbs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.core.native import NativeOwnership
from psx.renderers.components.scroll import (
    consume_scroll, scroll_axes, scroll_padding, scroll_props, updated_scroll_props,
)


class _ScrollFrame(ttk.Frame):
    """Exposes the actual Tk child master and wheel dispatch controller."""

    def __init__(self, master):
        super().__init__(master)
        self._psx_content = None
        self._psx_canvas = None
        self._psx_window = None
        self._psx_props = None
        self._psx_thumb_x = None
        self._psx_thumb_y = None
        self._psx_after = None
        self._psx_disposed = False

    def _bounds(self):
        canvas = self._psx_canvas
        inner = self._psx_content
        return (
            max(0, inner.winfo_reqwidth() - canvas.winfo_width()),
            max(0, inner.winfo_reqheight() - canvas.winfo_height()),
        )

    def _wheel(self, event):
        if self._psx_disposed or not self._psx_props["enabled"]:
            return None
        canvas = self._psx_canvas
        horizontal, vertical = scroll_axes(self._psx_props["direction"])
        is_horizontal = bool(event.state & 0x1) if hasattr(event, "state") else False
        permitted = horizontal if is_horizontal else vertical
        if not permitted:
            return None

        if getattr(event, "num", None) in (4, 5):
            delta = -40 if event.num == 4 else 40
        else:
            raw = getattr(event, "delta", 0)
            delta = -40 * (raw / 120) if raw else 0
        if not delta:
            return None
        limit_x, limit_y = self._bounds()
        limit = limit_x if is_horizontal else limit_y
        offset = canvas.canvasx(0) if is_horizontal else canvas.canvasy(0)
        new_position, remainder = consume_scroll(offset, limit, delta)
        if new_position != offset:
            if is_horizontal and limit_x:
                canvas.xview_moveto(new_position / max(1, self._psx_content.winfo_reqwidth()))
            elif limit_y:
                canvas.yview_moveto(new_position / max(1, self._psx_content.winfo_reqheight()))
            self._show_thumbs()
            return "break" if not remainder else None
        # Return an unconsumed delta for the nearest containing Scroll.
        return None

    def _show_thumbs(self):
        self._refresh()
        if self._psx_after is not None:
            self.after_cancel(self._psx_after)
        if self._psx_props["scrollbar"] == "auto":
            self._psx_after = self.after(750, self._hide_thumbs)
        else:
            self._psx_after = None

    def _hide_thumbs(self):
        self._psx_after = None
        if not self._psx_disposed:
            self._psx_canvas.delete("_psx_scroll_thumb")

    def _refresh(self, *_args):
        if self._psx_disposed:
            return
        canvas = self._psx_canvas
        frame = self._psx_content
        req_width, req_height = frame.winfo_reqwidth(), frame.winfo_reqheight()
        vp_width, vp_height = canvas.winfo_width(), canvas.winfo_height()
        enabled_x, enabled_y = scroll_axes(self._psx_props["direction"])
        canvas.itemconfigure(self._psx_window, width=max(req_width, vp_width) if not enabled_x else req_width,
                             height=max(req_height, vp_height) if not enabled_y else req_height)
        canvas.configure(scrollregion=(0, 0, max(req_width, vp_width), max(req_height, vp_height)))
        canvas.delete("_psx_scroll_thumb")
        if self._psx_props["scrollbar"] == "hidden":
            return
        if self._psx_props["scrollbar"] == "auto" and self._psx_after is None:
            return
        for axis, permitted, content, extent, view in (
            ("x", enabled_x, req_width, vp_width, canvas.xview()),
            ("y", enabled_y, req_height, vp_height, canvas.yview()),
        ):
            if not permitted or content <= extent or extent <= 1:
                continue
            fraction_start, fraction_end = view
            if axis == "x":
                canvas.create_rectangle(
                    3 + fraction_start * (vp_width - 6), vp_height - 8,
                    3 + fraction_end * (vp_width - 6), vp_height - 3,
                    fill="#888888", outline="", tags="_psx_scroll_thumb",
                )
            else:
                canvas.create_rectangle(
                    vp_width - 8, 3 + fraction_start * (vp_height - 6),
                    vp_width - 3, 3 + fraction_end * (vp_height - 6),
                    fill="#888888", outline="", tags="_psx_scroll_thumb",
                )

    def _teardown(self):
        self._psx_disposed = True
        if self._psx_after is not None:
            try:
                self.after_cancel(self._psx_after)
            except tk.TclError:
                pass
            self._psx_after = None


class TkScrollAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = scroll_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        outer = _ScrollFrame(master)
        canvas = tk.Canvas(outer, bd=0, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        content = ttk.Frame(canvas)
        outer._psx_canvas = canvas
        outer._psx_content = content
        outer._psx_window = canvas.create_window(0, 0, window=content, anchor=tk.NW)
        outer._psx_props = props
        content.bind("<Configure>", outer._refresh, add="+")
        canvas.bind("<Configure>", outer._refresh, add="+")
        self._apply(outer, props)
        return TkHandle("Scroll", outer, props)

    @staticmethod
    def _apply(outer, props):
        outer._psx_props = props
        if props["width"] is not None:
            outer._psx_canvas.configure(width=round(props["width"]))
        if props["height"] is not None:
            outer._psx_canvas.configure(height=round(props["height"]))
        outer._refresh()

    def update(self, renderer, handle, changed, removed):
        props = updated_scroll_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props
        self._repack(handle)

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
        if (
            child.native is not None
            and child.native.ownership is NativeOwnership.BORROWED
            and child.original_parent is not None
        ):
            child.widget.pack(in_=child.original_parent)
        self._repack(parent)
        return True

    @staticmethod
    def _repack(handle):
        props = handle.props
        inner = handle.widget._psx_content
        horizontal = props["content_direction"] == "horizontal"
        left, top, right, bottom = scroll_padding(props)
        for index, child in enumerate(handle.children):
            child.widget.pack_forget()
            options = {
                "side": tk.LEFT if horizontal else tk.TOP,
                "anchor": tk.NW,
                "padx": (left if index == 0 else props["spacing"], right if index == len(handle.children) - 1 else 0)
                       if horizontal else (left, right),
                "pady": (top, bottom) if horizontal else
                        (top if index == 0 else props["spacing"], bottom if index == len(handle.children) - 1 else 0),
            }
            child.widget.pack(in_=inner, **options)
        handle.widget._refresh()

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Scroll does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        outer = handle.widget
        outer._teardown()
        if outer.winfo_exists():
            outer.destroy()
