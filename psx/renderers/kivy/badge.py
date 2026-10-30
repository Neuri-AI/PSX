"""Portable Kivy Badge painted at its intrinsic size within parent layout slots."""

from __future__ import annotations

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.label import Label

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import (
    badge_props, badge_style, hex_rgba, updated_badge_props,
)

# Qt's existing Badge painter sets its font in typographic points.
# Convert those point tokens at CSS's 96 DPI, then project into Kivy's
# actual drawable space; do not assume every window is a 2x Retina display.
_CSS_PX_PER_POINT = 96.0 / 72.0


class _BadgeLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._psx_badge_props = None
        self._psx_badge_pixel_scale = 1.0
        self._psx_natural_size = (1.0, 1.0)
        self.bind(pos=self._redraw, size=self._on_size)

    def _on_size(self, *_args):
        # The layout may resize the Label after mount; center text within
        # the final slot while keeping the painted skin at its natural size.
        self.text_size = self.size
        self._redraw()

    def _redraw(self, *_args):
        props = self._psx_badge_props
        if props is None:
            return

        _fg, background, stroke, _font, _px, _py = badge_style(props)
        natural_width, natural_height = self._psx_natural_size
        # Row/Column own slot allocation. Never stretch the badge skin itself:
        # center its intrinsic rectangle within the assigned layout slot.
        width = min(self.width, natural_width)
        height = min(self.height, natural_height)
        x = self.x + (self.width - width) / 2
        y = self.y + (self.height - height) / 2
        radius = height / 2 if props["shape"] == "pill" else 5 * self._psx_badge_pixel_scale
        radius = min(radius, width / 2, height / 2)

        self.canvas.before.clear()
        with self.canvas.before:
            if background:
                Color(*hex_rgba(background))
                RoundedRectangle(pos=(x, y), size=(width, height), radius=[radius])
            if props["appearance"] == "outline":
                Color(*hex_rgba(stroke))
                # Stroke coordinates and width share the same drawable
                # density. A fixed 1px line becomes too thin on Retina.
                half = self._psx_badge_pixel_scale / 2
                Line(
                    rounded_rectangle=(
                        x + half, y + half,
                        max(0, width - 2 * half),
                        max(0, height - 2 * half),
                        max(0, radius - half),
                    ),
                    width=2 * half,
                )


class KivyBadgeAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = badge_props(node.props)
        widget = _BadgeLabel(size_hint=(None, None), halign="center", valign="middle")
        widget._psx_sfle_badge = renderer._sfle_constraints is not None
        widget._psx_badge_pixel_scale = getattr(renderer, "_psx_css_pixel_scale", 1.0)
        self._apply(widget, props)
        return KivyHandle("Badge", widget, props)

    @staticmethod
    def _apply(widget, props):
        foreground, _bg, _stroke, font_size, px, py = badge_style(props)
        widget._psx_badge_props = props
        widget.text = props["label"]
        scale = widget._psx_badge_pixel_scale
        widget.font_size = font_size * _CSS_PX_PER_POINT * scale
        widget.color = hex_rgba(foreground)

        # Measure text without constraints and preserve its natural width/height.
        widget.text_size = (None, None)
        widget.texture_update()
        width = max(1.0, widget.texture_size[0] + px * 2 * scale + 2 * scale)
        height = max(1.0, widget.texture_size[1] + py * 2 * scale + 2 * scale)
        widget._psx_natural_size = (width, height)
        if not widget._psx_sfle_badge:
            widget.size = (width, height)
        # Keep center-aligned label text in its allocated slot. Unlike sizing
        # the texture to the badge skin, this also works when Row stretches it.
        widget.text_size = widget.size
        widget.disabled = not props["enabled"]
        widget._redraw()

    def update(self, renderer, handle, changed, removed):
        props = updated_badge_props(handle.props, changed, removed)
        handle.widget._psx_badge_pixel_scale = getattr(renderer, "_psx_css_pixel_scale", 1.0)
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
