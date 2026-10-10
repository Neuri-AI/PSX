"""Built-in Radio and RadioGroup adapters for the Kivy renderer.

Kivy's CheckBox has a `group` attribute for mutual exclusion. Radio is a
BoxLayout containing a CheckBox and a Label. RadioGroup assigns a unique
group name to all its children and dispatches on_change when the active
checkbox changes.
"""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox as KivyCheckBox
from kivy.uix.label import Label

from psx.core.contracts import RADIO_DEFAULTS, RADIOGROUP_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.radio import (
    radio_props,
    radiogroup_props,
    updated_radio_props,
    updated_radiogroup_props,
)


class KivyRadioAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        props = radio_props({**RADIO_DEFAULTS, **node.props})

        widget = BoxLayout(orientation="horizontal", spacing=6, padding=0,
                           size_hint_y=None, height=32)
        checkbox = KivyCheckBox(size_hint=(None, None), size=(24, 24))
        label = Label(text=props["label"], halign="left", valign="middle")
        label.bind(size=lambda *_: setattr(label, "text_size", label.size))
        widget.add_widget(checkbox)
        widget.add_widget(label)

        widget._psx_checkbox = checkbox
        widget._psx_label = label
        widget._psx_radio_value = props["value"]
        widget.disabled = not props["enabled"]
        checkbox.disabled = not props["enabled"]

        return KivyHandle("Radio", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_radio_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget._psx_label.text = props["label"]
        widget._psx_radio_value = props["value"]
        widget.disabled = not props["enabled"]
        widget._psx_checkbox.disabled = not props["enabled"]

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Radio does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)


class KivyRadioGroupAdapter:
    _counter = 0

    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        props = radiogroup_props({**RADIOGROUP_DEFAULTS, **node.props})

        orientation = "vertical" if props["orientation"] == "vertical" else "horizontal"
        widget = BoxLayout(orientation=orientation,
                           spacing=int(props["spacing"]),
                           padding=_normalize_padding(props["padding"]),
                           size_hint_y=None)
        widget.bind(minimum_height=widget.setter("height"))

        KivyRadioGroupAdapter._counter += 1
        widget._psx_group_name = f"_psx_radio_group_{KivyRadioGroupAdapter._counter}"
        widget._psx_radios = {}          # value -> KivyCheckBox
        widget._psx_event_slot = None
        widget._psx_updating = False
        widget.disabled = not props["enabled"]

        return KivyHandle("RadioGroup", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_radiogroup_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget.spacing = int(props["spacing"])
        widget.padding = _normalize_padding(props["padding"])
        widget.disabled = not props["enabled"]

        if "value" in changed or "value" in removed:
            self._sync_checked(widget, props["value"])

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(
                f"RadioGroup does not emit {event!r}."
            )
        handle.widget._psx_event_slot = slot
        return None

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        if getattr(child, "node_type", None) != "Radio":
            raise RendererCapabilityError(
                "RadioGroup children must be Radio nodes."
            )
        widget = parent.widget
        value = child.props["value"]
        if value in widget._psx_radios:
            raise RendererCapabilityError(
                f"RadioGroup has duplicate Radio value {value!r}."
            )
        checkbox = child.widget._psx_checkbox
        checkbox.group = widget._psx_group_name
        checkbox.bind(active=lambda inst, active, v=value:
                      self._on_active(widget, v, active))
        widget._psx_radios[value] = checkbox
        widget.add_widget(child.widget)
        self._sync_checked(widget, parent.props["value"])
        return True

    def move(self, renderer, parent, child, index):
        widget = parent.widget
        widget.remove_widget(child.widget)
        widget.add_widget(child.widget, index=index)
        return True

    def remove(self, renderer, parent, child):
        widget = parent.widget
        value = child.props.get("value")
        if value is not None:
            widget._psx_radios.pop(value, None)
        widget.remove_widget(child.widget)
        return True

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _on_active(widget, value, active):
        if not active or widget._psx_updating:
            return
        slot = widget._psx_event_slot
        if slot is not None:
            slot.invoke(value)

    @staticmethod
    def _sync_checked(widget, selected_value):
        widget._psx_updating = True
        try:
            for value, checkbox in widget._psx_radios.items():
                checkbox.active = (value == selected_value)
        finally:
            widget._psx_updating = False


def _normalize_padding(value):
    if isinstance(value, int):
        return (value, value, value, value)
    if len(value) == 2:
        h, v = value
        return (h, v, h, v)
    return tuple(value)