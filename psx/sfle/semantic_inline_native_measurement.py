"""UI-thread font measurement ports for semantic inline fragments.

No extra native widgets are created for a word. The returned callback measures
the native font of the *existing* Text widget; CSS typography must already
have been applied to that widget. One callback lives for a single layout
transaction, so any per-run cache is invalidated on font/style changes.
"""
from __future__ import annotations

from collections.abc import Callable

from .semantic_inline_text import InlineTextMetrics


def qt_inline_measure(widgets: dict[str, object]) -> Callable[[str, str], InlineTextMetrics]:
    def measure(node_id: str, text: str) -> InlineTextMetrics:
        widget = widgets[node_id]
        font = widget.fontMetrics()
        return InlineTextMetrics(
            float(font.horizontalAdvance(text)),
            float(font.height()),
            float(font.ascent()),
        )
    return measure


def tk_inline_measure(widgets: dict[str, object]) -> Callable[[str, str], InlineTextMetrics]:
    from tkinter import font as tkfont
    from tkinter import ttk

    fonts = {}
    for node_id, widget in widgets.items():
        selected = widget.cget("font") if "font" in widget.keys() else ""
        if not selected and isinstance(widget, ttk.Widget):
            selected = ttk.Style(widget).lookup(widget.winfo_class(), "font")
        if not selected:
            selected = "TkDefaultFont"
        fonts[node_id] = tkfont.Font(root=widget, font=selected, exists=True) if isinstance(selected, str) and selected in tkfont.names(root=widget) else (
            tkfont.nametofont(selected, root=widget)
            if isinstance(selected, str) and selected in tkfont.names(root=widget)
            else tkfont.Font(root=widget, font=selected)
        )

    def measure(node_id: str, text: str) -> InlineTextMetrics:
        font = fonts[node_id]
        height = float(font.metrics("linespace"))
        baseline = float(font.metrics("ascent"))
        return InlineTextMetrics(float(font.measure(text)), height, min(baseline, height))
    return measure


def kivy_inline_measure(widgets: dict[str, object]) -> Callable[[str, str], InlineTextMetrics]:
    from kivy.core.text import Label as CoreLabel

    cache = {}

    def measure(node_id: str, text: str) -> InlineTextMetrics:
        widget = widgets[node_id]
        key = (
            text, widget.font_name, float(widget.font_size),
            bool(widget.bold), bool(widget.italic),
        )
        metrics = cache.get(key)
        if metrics is None:
            native = CoreLabel(
                text=text, font_name=widget.font_name,
                font_size=widget.font_size, bold=widget.bold, italic=widget.italic,
            )
            native.refresh()
            width, height = native.texture.size
            # Kivy's public SDL2 font provider supplies a texture line box,
            # not a stable font ascent. Existing Cinnamon baseline convention
            # uses the measured line box for these source Text widgets.
            metrics = InlineTextMetrics(float(width), float(height), float(height))
            cache[key] = metrics
        return metrics
    return measure
