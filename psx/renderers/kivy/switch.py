"""Labeled, animated Kivy Switch adapter."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.switch import Switch as KivySwitch

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.switch import SWITCH_SIZES, switch_props, updated_switch_props


class KivySwitchAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = switch_props(node.props)
        root = BoxLayout(orientation="horizontal", spacing=10, size_hint=(None, None))
        control = KivySwitch(size_hint=(None, None))
        root._psx_control = control
        root._psx_label = Label(halign="left", valign="middle", size_hint=(None, None))
        root._psx_updating = False
        root._psx_subscriptions = []
        root.add_widget(root._psx_label)
        root.add_widget(control)
        self._apply(root, props, initial=True)
        return KivyHandle("Switch", root, props)

    @staticmethod
    def _apply(root, props, *, initial=False):
        width, height = SWITCH_SIZES[props["size"]]
        root._psx_updating = True
        try:
            control = root._psx_control
            control.size = (width, height)
            control.disabled = not props["enabled"]
            # Kivy Switch animates user gestures natively. Controlled updates
            # synchronize active without emitting an on_change callback.
            control.active = props["checked"]
            root._psx_label.text = props["label"]
            root._psx_label.texture_update()
            label_width = root._psx_label.texture_size[0] if props["label"] else 0
            root._psx_label.size = (label_width, max(height, root._psx_label.texture_size[1]))
            root._psx_label.opacity = 1 if props["label"] else 0
            root.spacing = 10 if props["label"] else 0
            root.size = (width + (label_width + 10 if props["label"] else 0), height)
            root.disabled = not props["enabled"]
        finally:
            root._psx_updating = False

    def update(self, renderer, handle, changed, removed):
        props = updated_switch_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"Switch does not emit {event!r}.")
        root = handle.widget

        def changed(_instance, active):
            if not root._psx_updating:
                slot.invoke(bool(active))

        root._psx_control.bind(active=changed)
        return root._psx_control, changed

    def unbind_event(self, renderer, subscription):
        control, callback = subscription
        control.unbind(active=callback)

    def destroy(self, renderer, handle):
        root = handle.widget
        if root.parent is not None:
            root.parent.remove_widget(root)
