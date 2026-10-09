"""Built-in Column adapter for the Kivy renderer."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout

from psx.core.native import NativeOwnership
from psx.core.contracts import (
    COLUMN_DEFAULTS,
    validate_column_props,
)
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.column import (
    child_align,
    child_expand,
    normalize_padding,
    updated_column_props,
)


class KivyColumnAdapter:
    def create(self, renderer, node, parent):
        widget = BoxLayout(orientation="vertical")
        props = {**COLUMN_DEFAULTS, **node.props}
        validate_column_props(props)
        self._apply_container(widget, props)
        from psx.renderers.kivy.kivy import KivyHandle  # local import
        return KivyHandle("Column", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_column_props(handle.props, changed, removed)
        self._apply_container(handle.widget, props)
        handle.props = props
        self._reapply_children(handle)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Column does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    # -- hooks ------------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        container = parent
        if child in container.children:
            container.children.remove(child)
        container.children.insert(index, child)
        renderer._sync_children(container)
        self._reapply_children(container)
        return True

    def move(self, renderer, parent, child, index):
        container = parent
        container.children.remove(child)
        container.children.insert(index, child)
        renderer._sync_children(container)
        self._reapply_children(container)
        return True

    def remove(self, renderer, parent, child):
        container = parent
        if child in container.children:
            container.children.remove(child)
        container.widget.remove_widget(child.widget)
        if (
            child.native is not None
            and child.native.ownership is NativeOwnership.BORROWED
            and child.original_parent is not None
        ):
            child.original_parent.add_widget(child.widget)
        self._reapply_children(container)
        return True

    # -- helpers ----------------------------------------------------------

    def _apply_container(self, widget, props):
        l, t, r, b = normalize_padding(props["padding"])
        widget.padding = (l, t, r, b)
        widget.spacing = int(props["spacing"])
        widget.disabled = not bool(props["enabled"])

    def _reapply_children(self, container):
        for index, child in enumerate(container.children):
            widget = child.widget
            align = child_align(container.props, index)
            expand = child_expand(container.props, index)
            widget.size_hint_y = 1 if expand else None
            if align == "stretch":
                widget.size_hint_x = 1
                widget.pos_hint = {}
            else:
                widget.size_hint_x = None
                widget.pos_hint = {
                    "start": {"x": 0},
                    "center": {"center_x": 0.5},
                    "end": {"right": 1},
                }[align]
