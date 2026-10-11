"""F3-G2 Qt Flex host: native parenting only, never Qt layout geometry.

SFLE owns placement. This adapter deliberately does not construct
QHBoxLayout/QVBoxLayout and does not calculate sibling sizes.
"""
from __future__ import annotations

from psx.core.contracts import FLEX_CONTRACT
from psx.core.errors import RendererCapabilityError


class QtSFLEFlexAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        FLEX_CONTRACT.validate(node.props)
        widget = renderer._widget()
        return QtHandle("Flex", widget, props=dict(node.props))

    def update(self, renderer, handle, changed, removed):
        next_props = dict(handle.props)
        next_props.update(changed)
        for name in removed:
            next_props.pop(name, None)
        FLEX_CONTRACT.validate(next_props)
        handle.props = next_props

    def insert(self, renderer, parent, child, index):
        if child.widget.parentWidget() is not parent.widget:
            child.widget.setParent(parent.widget)
        child.widget.show()
        return True

    def move(self, renderer, parent, child, index):
        if child.widget.parentWidget() is not parent.widget:
            child.widget.setParent(parent.widget)
            child.widget.show()
        # Qt stacking order is not a Flex sizing mechanism.
        # PSX sibling order is recorded by the reconciler; geometry comes from SFLE.
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        _release(child)
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Flex does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()
