"""Portable animated Kivy Switch with an exactly sized track and right-side label."""

from __future__ import annotations

from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.switch import (
    SWITCH_SIZES,
    hex_rgb,
    switch_props,
    updated_switch_props,
)


class _SwitchTrack(ButtonBehavior, Widget):
    """Draw the track at the portable size, without Kivy's skin-size assumptions."""

    progress = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_color = "#16A34A"
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            progress=self._redraw,
            disabled=self._redraw,
        )
        self._redraw()

    def _redraw(self, *_args):
        red, green, blue = hex_rgb(self.active_color)
        t = max(0.0, min(1.0, self.progress))
        inactive = (0.612, 0.639, 0.686)
        active = (red / 255, green / 255, blue / 255)
        track = tuple(a + (b - a) * t for a, b in zip(inactive, active))
        if self.disabled:
            track = tuple(c * 0.55 + 0.45 for c in track)

        x, y = self.pos
        width, height = self.size
        diameter = max(0.0, height - 6)
        with self.canvas:
            self.canvas.clear()
            Color(*track, 1.0)
            RoundedRectangle(pos=(x, y), size=(width, height), radius=[height / 2])
            Color(1, 1, 1, 1)
            Ellipse(
                pos=(x + 3 + (width - height) * t, y + 3),
                size=(diameter, diameter),
            )


KIVY_SWITCH_SCALE = 2


class KivySwitchAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = switch_props(node.props)
        root = BoxLayout(
            orientation="horizontal", spacing=0, size_hint=(None, None)
        )
        track = _SwitchTrack(size_hint=(None, None))
        label = Label(
            halign="left", valign="middle",
            size_hint=(None, None),
        )
        root._psx_control = track
        root._psx_label = label
        root._psx_props = props
        # Kivy's BoxLayout lays out children in the order they are added.
        root.add_widget(track)
        root.add_widget(label)
        self._apply(root, props, initial=True)
        return KivyHandle("Switch", root, props)

    @staticmethod
    def _apply(root, props, *, initial=False):
        base_width, base_height = SWITCH_SIZES[props["size"]]
        width, height = base_width * KIVY_SWITCH_SCALE, base_height * KIVY_SWITCH_SCALE
        track = root._psx_control
        track.size = (width, height)
        track.active_color = props["color"]
        track.disabled = not props["enabled"]
        label = root._psx_label
        label.text = props["label"]
        label.texture_update()
        label_width = label.texture_size[0] if props["label"] else 0
        root.spacing = 10 if props["label"] else 0
        label.size = (label_width, max(height, label.texture_size[1]))
        label.opacity = 1 if props["label"] else 0
        root.size = (
            width + (label_width + 10 if props["label"] else 0),
            max(height, label.height),
        )
        root.disabled = not props["enabled"]
        Animation.cancel_all(track, "progress")
        target = float(props["checked"])
        if initial:
            track.progress = target
        elif abs(track.progress - target) > 0.0001:
            Animation(progress=target, d=0.16, t="out_cubic").start(track)
        else:
            track._redraw()

    def update(self, renderer, handle, changed, removed):
        props = updated_switch_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.widget._psx_props = props
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"Switch does not emit {event!r}.")
        root = handle.widget
        track = root._psx_control

        def clicked(_instance):
            if root._psx_props["enabled"]:
                slot.invoke(not root._psx_props["checked"])

        track.bind(on_release=clicked)
        return track, clicked

    def unbind_event(self, renderer, subscription):
        track, callback = subscription
        track.unbind(on_release=callback)

    def destroy(self, renderer, handle):
        root = handle.widget
        Animation.cancel_all(root._psx_control, "progress")
        if root.parent is not None:
            root.parent.remove_widget(root)
