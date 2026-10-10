"""Built-in RadioGroup adapter for the Qt renderer.

Radio itself is a register_primitive; RadioGroup coordinates the exclusive
selection using a QButtonGroup and dispatches on_change with the value of
the newly selected radio.
"""

from __future__ import annotations

import importlib

from psx.core.contracts import RADIOGROUP_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.radio import (
    radiogroup_props,
    updated_radiogroup_props,
)


class QtRadioGroupAdapter:
    def __init__(self, *, widget_class, layout_h, layout_v, binding_package):
        self._widget_class = widget_class
        self._layout_h = layout_h
        self._layout_v = layout_v
        self._binding_package = binding_package

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        widgets = importlib.import_module(f"{self._binding_package}.QtWidgets")
        props = radiogroup_props({**RADIOGROUP_DEFAULTS, **node.props})

        widget = self._widget_class()
        layout = self._layout_h(widget) if props["orientation"] == "horizontal" \
            else self._layout_v(widget)
        left, top, right, bottom = _normalize_padding(props["padding"])
        layout.setContentsMargins(left, top, right, bottom)
        layout.setSpacing(int(props["spacing"]))
        widget.setEnabled(bool(props["enabled"]))

        button_group = widgets.QButtonGroup(widget)
        button_group.setExclusive(True)
        widget._psx_button_group = button_group
        widget._psx_radios = {}          # value -> QRadioButton
        widget._psx_event_slot = None
        widget._psx_updating = False

        button_group.buttonToggled.connect(
            lambda button, checked: self._on_button_toggled(widget, button, checked)
        )

        return QtHandle("RadioGroup", widget, layout=layout, props=props)

    def update(self, renderer, handle, changed, removed):
        props = updated_radiogroup_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        layout = handle.layout

        layout.setSpacing(int(props["spacing"]))
        left, top, right, bottom = _normalize_padding(props["padding"])
        layout.setContentsMargins(left, top, right, bottom)
        widget.setEnabled(bool(props["enabled"]))

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
        handle.widget.setParent(None)
        handle.widget.deleteLater()

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        from psx.renderers.qt.pyqt import _release
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
        widget._psx_radios[value] = child.widget
        parent.layout.insertWidget(index, child.widget)
        widget._psx_button_group.addButton(child.widget)
        child.widget._psx_radio_value = value
        # Apply the current selection to the newly inserted child.
        self._sync_checked(widget, parent.props["value"])
        return True

    def move(self, renderer, parent, child, index):
        parent.layout.removeWidget(child.widget)
        parent.layout.insertWidget(index, child.widget)
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        widget = parent.widget
        value = child.props.get("value")
        if value is not None:
            widget._psx_radios.pop(value, None)
        widget._psx_button_group.removeButton(child.widget)
        parent.layout.removeWidget(child.widget)
        _release(child)
        return True

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _on_button_toggled(widget, button, checked):
        if not checked or widget._psx_updating:
            return
        value = getattr(button, "_psx_radio_value", None)
        slot = widget._psx_event_slot
        if slot is not None and value is not None:
            slot.invoke(value)

    @staticmethod
    def _sync_checked(widget, selected_value):
        """Reflect the group's value on its radios without firing signals."""
        widget._psx_updating = True
        try:
            for value, radio in widget._psx_radios.items():
                should_check = value == selected_value
                if radio.isChecked() != should_check:
                    radio.setChecked(should_check)
        finally:
            widget._psx_updating = False


def make_qt_radiogroup_adapter(renderer):
    return QtRadioGroupAdapter(
        widget_class=renderer._widget,
        layout_h=renderer._hbox,
        layout_v=renderer._vbox,
        binding_package=renderer._binding_package,
    )


def _normalize_padding(value):
    if isinstance(value, int):
        return (value, value, value, value)
    if len(value) == 2:
        h, v = value
        return (h, v, h, v)
    return tuple(value)