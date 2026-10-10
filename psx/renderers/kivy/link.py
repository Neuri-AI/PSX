"""Portable Kivy Link adapter with user activation and explicit subscriptions."""

from __future__ import annotations

from kivy.uix.button import Button

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.link import activate_link, link_props, updated_link_props


def _escape_markup(value: str) -> str:
    return value.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


class KivyLinkAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = link_props(node.props)
        widget = Button(
            size_hint=(None, None), background_normal="",
            background_down="", background_color=(0, 0, 0, 0),
            markup=True, halign="left",
        )
        widget._psx_link_props = props
        widget.bind(on_release=lambda *_: activate_link(widget._psx_link_props))
        self._apply(widget, props)
        return KivyHandle("Link", widget, props)

    @staticmethod
    def _apply(widget, props):
        widget._psx_link_props = props
        color = (props["color"] or "#2563EB").lstrip("#")
        rgb = tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
        widget.color = (*rgb, 1)
        text = _escape_markup(props["label"])
        widget.text = f"[u]{text}[/u]" if props["underline"] else text
        widget.disabled = not props["enabled"]
        widget.texture_update()
        widget.size = (max(1, widget.texture_size[0] + 4), max(24, widget.texture_size[1] + 4))

    def update(self, renderer, handle, changed, removed):
        props = updated_link_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_click":
            raise RendererCapabilityError(f"Link does not emit {event!r}.")
        widget = handle.widget
        callback = lambda *_: slot.invoke()
        widget.bind(on_release=callback)
        return widget, callback

    def unbind_event(self, renderer, subscription):
        widget, callback = subscription
        widget.unbind(on_release=callback)

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)
