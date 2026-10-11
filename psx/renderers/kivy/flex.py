"""F3-G2 Kivy Flex host: explicit geometry, zero Kivy layout authority.

Kivy Widget is not a BoxLayout. SFLE alone controls child rectangles and
Kivy's bottom-left projection happens at native geometry commit, not here.
"""
from __future__ import annotations

from kivy.uix.widget import Widget

from psx.core.contracts import FLEX_CONTRACT
from psx.core.errors import RendererCapabilityError


class KivySFLEFlexAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        FLEX_CONTRACT.validate(node.props)
        widget = Widget(size_hint=(None, None))
        widget.pos_hint = {}
        if parent is None:
            constraints = renderer._sfle_constraints
            if constraints.width.value is None or constraints.height.value is None:
                raise RendererCapabilityError("Kivy SFLE root needs definite viewport dimensions.")
            widget.size = (constraints.width.value, constraints.height.value)
            renderer._root = widget
        return KivyHandle("Flex", widget, dict(node.props))

    def update(self, renderer, handle, changed, removed):
        props = dict(handle.props)
        props.update(changed)
        for key in removed:
            props.pop(key, None)
        FLEX_CONTRACT.validate(props)
        handle.props = props

    @staticmethod
    def _sync(handle):
        container = handle.widget
        desired = [item.widget for item in reversed(handle.children)]
        # Kivy's Widget.children list is reverse declaration order.
        for item in tuple(container.children):
            if item not in desired:
                container.remove_widget(item)
        for index, widget in enumerate(desired):
            widget.size_hint = (None, None)
            widget.pos_hint = {}
            if widget.parent is not container:
                container.add_widget(widget, index=index)
            elif container.children.index(widget) != index:
                container.remove_widget(widget)
                container.add_widget(widget, index=index)

    def insert(self, renderer, parent, child, index):
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        self._sync(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.children.remove(child)
        parent.children.insert(index, child)
        self._sync(parent)
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.kivy.kivy import _is_borrowed
        if child in parent.children:
            parent.children.remove(child)
        if child.widget.parent is parent.widget:
            parent.widget.remove_widget(child.widget)
        if _is_borrowed(child) and child.original_parent is not None:
            child.original_parent.add_widget(child.widget)
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Flex does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)
        if renderer._root is widget:
            renderer._root = None
