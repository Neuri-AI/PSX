"""qt native inline text fragment painting.

The renderer owns its painter and widget teardown. Cinnamon only supplies
immutable geometry and native glyph measurement metadata.
"""
from __future__ import annotations

def paint(widget, fragments, box, binding):
    import importlib

    core = importlib.import_module(f"{binding}.QtCore")
    gui = importlib.import_module(f"{binding}.QtGui")

    if not hasattr(widget, "_psx_semantic_inline_filter"):
        class InlineFilter(core.QObject):
            def __init__(self, owner):
                super().__init__(owner)
                self.fragments = ()
                self.rect = None

            def eventFilter(self, target, event):
                kind = getattr(core.QEvent, "Type", core.QEvent).Paint
                if event.type() != kind:
                    return False
                if not self.fragments:
                    return False
                painter = gui.QPainter(target)
                painter.setFont(target.font())
                painter.setPen(target.palette().color(target.foregroundRole()))
                for chunk in self.fragments:
                    painter.drawText(
                        core.QPointF(
                            chunk.x - self.rect.x,
                            chunk.y - self.rect.y + chunk.baseline,
                        ),
                        chunk.text,
                    )
                painter.end()
                return True

        filt = InlineFilter(widget)
        widget.installEventFilter(filt)
        widget._psx_semantic_inline_filter = filt
    filt = widget._psx_semantic_inline_filter
    filt.fragments, filt.rect = fragments, box
    widget.update()


def clear(widget):
    filt = getattr(widget, "_psx_semantic_inline_filter", None)
    if filt is not None:
        widget.removeEventFilter(filt)
        del widget._psx_semantic_inline_filter
        widget.update()
