"""kivy native inline glyph metrics port (renderer-owned)."""
from __future__ import annotations
from collections.abc import Callable
from psx.layout.inline.semantic_inline_text import InlineTextMetrics

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
