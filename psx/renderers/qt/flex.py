"""Native SFLE Qt Flex host: native parenting only, never Qt layout geometry.

SFLE owns placement. This adapter deliberately does not construct
QHBoxLayout/QVBoxLayout and does not calculate sibling sizes.
"""
from __future__ import annotations

from psx.core.contracts import FLEX_CONTRACT
from psx.core.errors import RendererCapabilityError


_ROOT_FLEX_WIDGET_TYPES = {}


def _root_flex_widget_type(base_widget):
    widget_type = _ROOT_FLEX_WIDGET_TYPES.get(base_widget)
    if widget_type is not None:
        return widget_type

    class RootFlexWidget(base_widget):
        """Proxy external window operations to the stable native viewport."""

        def show(self):
            shell = getattr(self, "_psx_sfle_viewport_shell", None)
            if shell is not None:
                shell.show()
            super().show()

        def resize(self, *args):
            shell = getattr(self, "_psx_sfle_viewport_shell", None)
            if shell is not None:
                shell.resize(*args)
                return
            super().resize(*args)

    _ROOT_FLEX_WIDGET_TYPES[base_widget] = RootFlexWidget
    return RootFlexWidget


class QtSFLEFlexAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        FLEX_CONTRACT.validate(node.props)
        widget = (_root_flex_widget_type(renderer._widget)()
                  if parent is None and renderer._sfle_constraints is not None
                  else renderer._widget())
        if parent is None and renderer._sfle_constraints is not None:
            viewport = renderer._widget()
            viewport.resize(round(renderer._sfle_constraints.width.value),
                            round(renderer._sfle_constraints.height.value))
            widget.setParent(viewport)
            widget._psx_sfle_viewport_shell = viewport
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
        shell = getattr(handle.widget, "_psx_sfle_viewport_shell", None)
        handle.widget.setParent(None)
        handle.widget.deleteLater()
        if shell is not None:
            shell.close()
            shell.deleteLater()
