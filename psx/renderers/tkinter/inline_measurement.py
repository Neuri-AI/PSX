"""tkinter native inline glyph metrics port (renderer-owned)."""
from __future__ import annotations
from collections.abc import Callable
from psx.layout.inline.semantic_inline_text import InlineTextMetrics

def tk_inline_measure(widgets: dict[str, object]) -> Callable[[str, str], InlineTextMetrics]:
    from tkinter import font as tkfont
    from tkinter import ttk

    fonts = {}
    for node_id, widget in widgets.items():
        selected = widget.cget("font") if "font" in widget.keys() else ""
        if not selected and isinstance(widget, ttk.Widget):
            style_name = (widget.cget("style") if "style" in widget.keys()
                          else "") or widget.winfo_class()
            selected = ttk.Style(widget).lookup(style_name, "font")
        if not selected:
            selected = "TkDefaultFont"
        # Copy Tcl's actual font attributes into a transaction-local font.
        # The constructor accepts both named fonts and Tk font descriptions.
        fonts[node_id] = tkfont.Font(root=widget, font=selected)

    def measure(node_id: str, text: str) -> InlineTextMetrics:
        font = fonts[node_id]
        height = float(font.metrics("linespace"))
        baseline = float(font.metrics("ascent"))
        return InlineTextMetrics(float(font.measure(text)), height, min(baseline, height))
    return measure
