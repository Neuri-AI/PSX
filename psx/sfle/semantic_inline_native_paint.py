"""Paint Cinnamon inline glyph fragments without per-word native widgets.

Each source Text owns exactly its original QLabel/ttk.Label/Kivy Label.
Qt installs one paint-event filter, Tk overlays one canvas inside the existing
label, and Kivy paints font textures in its existing Label canvas.
"""
from __future__ import annotations

from collections.abc import Mapping

from .semantic_inline_text import InlineTextFragment


def _qt_paint(widget, fragments, box, binding):
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


def _qt_clear(widget):
    filt = getattr(widget, "_psx_semantic_inline_filter", None)
    if filt is not None:
        widget.removeEventFilter(filt)
        del widget._psx_semantic_inline_filter
        widget.update()


def _tk_paint(widget, fragments, box):
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
    font = widget.cget("font") if "font" in widget.keys() else ""
    if not font:
        font = style.lookup(widget.winfo_class(), "font") or "TkDefaultFont"
    color = (style.lookup(widget.winfo_class(), "foreground")
             or widget.cget("foreground"))
    for f in fragments:
        if f.text.isspace():
            continue
        surface.create_text(
            round(f.x - box.x), round(f.y - box.y),
            text=f.text, anchor="nw", font=font, fill=color,
        )


def _tk_clear(widget):
    surface = getattr(widget, "_psx_semantic_inline_canvas", None)
    if surface is not None:
        surface.destroy()
        del widget._psx_semantic_inline_canvas


def _kivy_paint(widget, fragments, box):
    from kivy.core.text import Label as CoreLabel
    from kivy.graphics import Color, InstructionGroup, Rectangle

    former = getattr(widget, "_psx_semantic_inline_paint", None)
    if former is not None:
        group, redraw, original, previous_tint = former
        widget.unbind(pos=redraw, size=redraw)
        widget.canvas.after.remove(group)
    else:
        previous_tint = tuple(widget.color)
    if tuple(widget.color) != (0.0, 0.0, 0.0, 0.0):
        tint = tuple(widget.color)
    else:
        tint = previous_tint

    group = InstructionGroup()
    group.add(Color(*tint))
    rectangles = []
    for f in fragments:
        if f.text.isspace():
            continue
        label = CoreLabel(
            text=f.text, font_name=widget.font_name,
            font_size=widget.font_size, bold=widget.bold, italic=widget.italic,
        )
        label.refresh()
        rect = Rectangle(texture=label.texture, size=label.texture.size)
        group.add(rect)
        rectangles.append((f, rect))

    def redraw(*_):
        for f, rect in rectangles:
            rect.pos = (
                widget.x + f.x - box.x,
                widget.top - (f.y - box.y) - rect.size[1],
            )
    widget.canvas.after.add(group)
    widget.bind(pos=redraw, size=redraw)
    widget.color = (0, 0, 0, 0)
    widget._psx_semantic_inline_paint = (group, redraw, tuple(tint), tuple(tint))
    redraw()


def _kivy_clear(widget):
    former = getattr(widget, "_psx_semantic_inline_paint", None)
    if former is not None:
        group, redraw, original, _ = former
        widget.unbind(pos=redraw, size=redraw)
        widget.canvas.after.remove(group)
        widget.color = original
        del widget._psx_semantic_inline_paint


def project_native_inline_paint(
    renderer,
    backend: str,
    widgets: Mapping[str, object],
    fragment_plan: Mapping[str, tuple[InlineTextFragment, ...]],
    boxes,
) -> None:
    """Repaint only original source Text hosts after Cinnamon's native commit.

    Called on each backend's owning UI thread, never from a worker.
    """
    clear = {"qt": _qt_clear, "tk": _tk_clear, "kivy": _kivy_clear}[backend]
    previous = getattr(renderer, "_sfle_semantic_inline_widgets", {})
    next_widgets = {node_id: widgets[node_id] for node_id in fragment_plan}
    for node_id, widget in previous.items():
        if next_widgets.get(node_id) is not widget:
            try:
                clear(widget)
            except (RuntimeError, AttributeError, ValueError):
                # A native owner may already have destroyed the widget.
                pass
    for node_id, fragments in fragment_plan.items():
        widget = widgets[node_id]
        box = boxes[node_id].content
        if backend == "qt":
            _qt_paint(widget, fragments, box, renderer._binding_package)
        elif backend == "tk":
            _tk_paint(widget, fragments, box)
        else:
            _kivy_paint(widget, fragments, box)
    renderer._sfle_semantic_inline_widgets = next_widgets
