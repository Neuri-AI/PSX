"""qt native inline glyph metrics port (renderer-owned)."""
from __future__ import annotations
from collections.abc import Callable
from psx.layout.inline.semantic_inline_text import InlineTextMetrics

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
