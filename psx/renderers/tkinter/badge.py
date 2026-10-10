"""Portable Tkinter Badge using themed canvas surfaces and rounded geometry."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import badge_props, badge_style, updated_badge_props


def _surface_color(widget: tk.Misc) -> str:
    """Resolve an actual container surface instead of Tk Canvas' white default.

    ttk widgets generally do not expose a `background` option through cget().
    Root's explicit background is preferred to avoid introducing bright corners
    into dark-themed windows; ttk style lookup is a fallback.
    """
    root = widget.winfo_toplevel()
    try:
        background = root.cget("background")
        if background:
            return str(background)
    except tk.TclError:
        pass

    style = ttk.Style(widget)
    current = widget
    while current is not None:
        try:
            name = current.cget("style")
        except (tk.TclError, AttributeError):
            name = ""
        if not name:
            try:
                name = current.winfo_class()
            except tk.TclError:
                name = "TFrame"
        background = style.lookup(str(name), "background")
        if background:
            return str(background)
        current = getattr(current, "master", None)
    return "#303030"


def _rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline):
    """Compose rounded corners with native arcs and rectangles.

    Canvas does not support actual transparency or anti-aliased paths; keeping
    curves inside the bounds avoids white corner artifacts.
    """
    r = max(0, min(float(radius), (x2 - x1) / 2, (y2 - y1) / 2))
    if r < 1:
        canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline)
        return

    # Fill each quarter-circle and the two connecting rectangles.
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
    for x, y, start in (
        (x1, y1, 90),
        (x2 - 2 * r, y1, 0),
        (x2 - 2 * r, y2 - 2 * r, 270),
        (x1, y2 - 2 * r, 180),
    ):
        canvas.create_arc(
            x, y, x + 2 * r, y + 2 * r,
            start=start, extent=90,
            style=tk.PIESLICE, fill=fill, outline="",
        )

    if not outline:
        return
    # Draw a clean outline with quarter arcs and straight segments.
    canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline)
    canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline)
    canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline)
    canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline)
    for x, y, start in (
        (x1, y1, 90),
        (x2 - 2 * r, y1, 0),
        (x2 - 2 * r, y2 - 2 * r, 270),
        (x1, y2 - 2 * r, 180),
    ):
        canvas.create_arc(
            x, y, x + 2 * r, y + 2 * r,
            start=start, extent=90,
            style=tk.ARC, outline=outline,
        )


class TkBadgeAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = badge_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        canvas = tk.Canvas(
            master, highlightthickness=0, bd=0, relief="flat",
            background=_surface_color(master),
        )
        canvas._psx_badge_font = tkfont.Font(canvas, size=12)
        self._apply(canvas, props)
        return TkHandle("Badge", canvas, props)

    @staticmethod
    def _apply(canvas, props):
        foreground, background, stroke, font_size, px, py = badge_style(props)
        font = canvas._psx_badge_font
        font.configure(size=font_size)

        width = max(1, font.measure(props["label"]) + px * 2 + 4)
        height = max(1, font.metrics("linespace") + py * 2 + 4)
        surface = _surface_color(canvas.master)
        canvas.configure(width=width, height=height, background=surface)
        canvas.delete("all")

        radius = height / 2 if props["shape"] == "pill" else 5
        _rounded_rect(
            canvas, 1, 1, width - 2, height - 2, radius,
            fill=background or surface,
            outline=stroke if props["appearance"] == "outline" else "",
        )
        text_item = canvas.create_text(
            width / 2, height / 2,
            text=props["label"], fill=foreground, font=font, anchor="center",
        )
        # Tk's font metrics and Canvas anchor geometry differ slightly from
        # Qt on macOS. Align the actual rendered text bounding box rather
        # than relying on its nominal baseline/anchor alone.
        if props["label"]:
            bounds = canvas.bbox(text_item)
            if bounds is not None:
                actual_center_y = (bounds[1] + bounds[3]) / 2
                canvas.move(text_item, 0, round(height / 2 - actual_center_y))

    def update(self, renderer, handle, changed, removed):
        props = updated_badge_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Badge does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.winfo_exists():
            widget.destroy()
