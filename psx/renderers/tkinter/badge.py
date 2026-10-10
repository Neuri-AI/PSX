"""Portable Tkinter Badge drawn with per-widget canvas shapes and text."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import badge_props, badge_style, updated_badge_props


def _rounded_path(canvas, x1, y1, x2, y2, radius, *, fill, outline):
    """Draw a rounded rectangle with a smooth closed polygon."""
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    coords = [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    canvas.create_polygon(
        coords, smooth=True, splinesteps=20,
        fill=fill, outline=outline, width=1,
    )


class TkBadgeAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = badge_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        canvas = tk.Canvas(master, highlightthickness=0, bd=0, relief="flat")
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
        # A transparent Canvas is not supported by Tk. Match the parent surface
        # when painting an outlined badge.
        try:
            background_color = canvas.master.cget("background")
        except tk.TclError:
            background_color = "#F0F0F0"
        try:
            canvas.configure(background=background_color)
        except tk.TclError:
            background_color = "#F0F0F0"
            canvas.configure(background=background_color)
        canvas.configure(width=width, height=height)
        canvas.delete("all")
        radius = height / 2 if props["shape"] == "pill" else 5
        _rounded_path(
            canvas, 1, 1, width - 1, height - 1, radius,
            fill=background or background_color,
            outline=stroke if props["appearance"] == "outline" else background,
        )
        canvas.create_text(
            width / 2, height / 2, text=props["label"],
            fill=foreground, font=font, anchor="center",
        )

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
