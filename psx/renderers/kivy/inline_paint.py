"""kivy native inline text fragment painting.

The renderer owns its painter and widget teardown. Cinnamon only supplies
immutable geometry and native glyph measurement metadata.
"""
from __future__ import annotations

def paint(widget, fragments, box):
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

    from collections import OrderedDict
    cache = getattr(widget, "_psx_semantic_inline_texture_cache", None)
    if cache is None:
        cache = OrderedDict()
        widget._psx_semantic_inline_texture_cache = cache

    group = InstructionGroup()
    group.add(Color(*tint))
    rectangles = []
    for f in fragments:
        if f.text.isspace():
            continue
        key = (f.text, widget.font_name, float(widget.font_size),
               bool(widget.bold), bool(widget.italic))
        texture = cache.get(key)
        if texture is None:
            label = CoreLabel(
                text=f.text, font_name=widget.font_name,
                font_size=widget.font_size, bold=widget.bold, italic=widget.italic,
            )
            label.refresh()
            texture = label.texture
            cache[key] = texture
            if len(cache) > 128:
                cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        rect = Rectangle(texture=texture, size=texture.size)
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


def clear(widget):
    former = getattr(widget, "_psx_semantic_inline_paint", None)
    if former is not None:
        group, redraw, original, _ = former
        widget.unbind(pos=redraw, size=redraw)
        widget.canvas.after.remove(group)
        widget.color = original
        del widget._psx_semantic_inline_paint
        if hasattr(widget, "_psx_semantic_inline_texture_cache"):
            del widget._psx_semantic_inline_texture_cache
