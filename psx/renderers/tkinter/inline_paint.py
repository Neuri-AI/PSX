"""tkinter native inline text fragment painting.

The renderer owns its painter and widget teardown. Cinnamon only supplies
immutable geometry and native glyph measurement metadata.
"""
from __future__ import annotations

def paint(widget, fragments, box):
    import tkinter as tk
    from tkinter import ttk

    surface = getattr(widget, "_psx_semantic_inline_canvas", None)
    if surface is None:
        surface = tk.Canvas(
            widget, borderwidth=0, highlightthickness=0,
            takefocus=0,
        )
        widget._psx_semantic_inline_canvas = surface
    ancestor = widget.master
    background = None
    while ancestor is not None:
        background = getattr(ancestor, "_psx_css_background", None)
        if background is not None:
            break
        ancestor = getattr(ancestor, "master", None)
    style = ttk.Style(widget)
    if not background:
        background = style.lookup("TLabel", "background") or widget.winfo_toplevel().cget("background")
    surface.configure(background=background)
    surface.place(x=0, y=0, relwidth=1, relheight=1)
    surface.delete("all")
    # PSX assigns a widget-specific ttk style for authored CSS color/font.
    # TLabel would silently fall back to the theme instead of the span's red.
    style_name = (widget.cget("style") if "style" in widget.keys()
                  else "") or widget.winfo_class()
    font = widget.cget("font") if "font" in widget.keys() else ""
    if not font:
        font = style.lookup(style_name, "font") or "TkDefaultFont"
    color = style.lookup(style_name, "foreground") or widget.cget("foreground")
    for f in fragments:
        if f.text.isspace():
            continue
        surface.create_text(
            round(f.x - box.x), round(f.y - box.y),
            text=f.text, anchor="nw", font=font, fill=color,
        )


def clear(widget):
    surface = getattr(widget, "_psx_semantic_inline_canvas", None)
    if surface is not None:
        surface.destroy()
        del widget._psx_semantic_inline_canvas
