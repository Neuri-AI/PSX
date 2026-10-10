"""Internal passthrough container adapter for the Kivy renderer."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout

from psx.core.errors import RendererCapabilityError


class KivyBoxAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        widget = BoxLayout(orientation="vertical", padding=0, spacing=0)
        return KivyHandle("Box", widget, dict(node.props))

    def update(self, renderer, handle, changed, removed):
        if changed or removed:
            raise RendererCapabilityError(
                f"Box is an internal container and does not accept props: "
                f"{', '.join(sorted(set(changed) | removed))}"
            )

    def insert(self, renderer, parent, child, index):
        widget = parent.widget
        child_widget = child.widget
        child_widget.size_hint = (1, 1)
        widget.add_widget(child_widget, index=0)
        return True

    def move(self, renderer, parent, child, index):
        # Only one child can ever be present; reordering is a no-op.
        return True

    def remove(self, renderer, parent, child):
        parent.widget.remove_widget(child.widget)
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Box does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)