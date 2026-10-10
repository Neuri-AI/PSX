"""Portable Qt Link adapter using a native focusable flat QPushButton."""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.link import activate_link, link_props, updated_link_props


class QtLinkAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = link_props(node.props)
        core = importlib.import_module(f"{renderer._binding_package}.QtCore")
        widget = renderer._widgets.QPushButton()
        widget.setFlat(True)
        widget.setCursor(getattr(getattr(core.Qt, "CursorShape", core.Qt), "PointingHandCursor"))
        widget._psx_link_props = props
        widget.clicked.connect(lambda *_: activate_link(widget._psx_link_props))
        self._apply(widget, props)
        return QtHandle("Link", widget, props=props)

    @staticmethod
    def _apply(widget, props):
        widget._psx_link_props = props
        widget.setText(props["label"])
        widget.setEnabled(props["enabled"])
        font = widget.font()
        font.setUnderline(props["underline"])
        widget.setFont(font)
        color = props["color"] or "#2563EB"
        widget.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"padding: 0px; text-align: left; color: {color}; }}"
        )
        widget.setAccessibleName(props["label"])
        widget.adjustSize()

    def update(self, renderer, handle, changed, removed):
        props = updated_link_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_click":
            raise RendererCapabilityError(f"Link does not emit {event!r}.")
        signal = handle.widget.clicked
        callback = lambda *_: slot.invoke()
        signal.connect(callback)
        return signal, callback

    def unbind_event(self, renderer, subscription):
        signal, callback = subscription
        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            pass

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()
