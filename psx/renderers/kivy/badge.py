"""Portable Kivy Badge with a rounded canvas skin and intrinsic width."""

from __future__ import annotations

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.label import Label

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import (
    badge_props, badge_style, hex_rgba, updated_badge_props,
)


class _BadgeLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._psx_badge_props = None
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args):
        props = self._psx_badge_props
        if props is None:
            return
        _fg, background, stroke, _font, _px, _py = badge_style(props)
        radius = self.height / 2 if props["shape"] == "pill" else 5
        with self.canvas.before:
            self.canvas.before.clear()
            if background:
                Color(*hex_rgba(background))
                RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            if props["appearance"] == "outline":
                Color(*hex_rgba(stroke))
                Line(rounded_rectangle=(
                    self.x + 0.5, self.y + 0.5,
                    max(0, self.width - 1), max(0, self.height - 1),
                    radius,
                ), width=1)


class KivyBadgeAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = badge_props(node.props)
        widget = _BadgeLabel(size_hint=(None, None), halign="center", valign="middle")
        self._apply(widget, props)
        return KivyHandle("Badge", widget, props)

    @staticmethod
    def _apply(widget, props):
        foreground, _bg, _stroke, font_size, px, py = badge_style(props)
        widget._psx_badge_props = props
        widget.text = props["label"]
        widget.font_size = font_size
        widget.color = hex_rgba(foreground)
        widget.text_size = (None, None)
        widget.texture_update()
        width = max(1, widget.texture_size[0] + px * 2 + 2)
        height = max(1, widget.texture_size[1] + py * 2 + 2)
        widget.size = (width, height)
        widget.text_size = (width, height)
        widget.disabled = not props["enabled"]
        widget._redraw()

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
        widget.canvas.before.clear()
        if widget.parent is not None:
            widget.parent.remove_widget(widget)
