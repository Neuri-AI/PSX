"""Kivy ScrollView with managed multi-child content and overlay indicators."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView

from psx.core.errors import RendererCapabilityError
from psx.core.native import NativeOwnership
from psx.renderers.components.scroll import (
    scroll_axes, scroll_padding, scroll_props, updated_scroll_props,
)


class _PSXScrollView(ScrollView):
    """Pass unconsumed mouse-wheel input to the enclosing ScrollView."""

    def on_scroll_start(self, touch, check_children=True):
        props = getattr(self, "_psx_props", None)
        if props is not None:
            if not props["enabled"]:
                return False
            horizontal, vertical = scroll_axes(props["direction"])
            button = getattr(touch, "button", "")
            # A nested viewport must not consume a wheel event it cannot use.
            # Returning False allows Kivy's enclosing ScrollView to receive it.
            if button == "scrollup" and (
                not vertical or self.scroll_y >= 1.0 or
                self._psx_content.height <= self.height
            ):
                return False
            if button == "scrolldown" and (
                not vertical or self.scroll_y <= 0.0 or
                self._psx_content.height <= self.height
            ):
                return False
            if button == "scrollleft" and (
                not horizontal or self.scroll_x <= 0.0 or
                self._psx_content.width <= self.width
            ):
                return False
            if button == "scrollright" and (
                not horizontal or self.scroll_x >= 1.0 or
                self._psx_content.width <= self.width
            ):
                return False
        return super().on_scroll_start(touch, check_children=check_children)

    def on_touch_down(self, touch):
        # SDL2 on macOS commonly exposes two-finger trackpad scrolling as
        # scroll-button touches. Delegate to the standard Kivy ScrollView
        # first (including nested children); if it did not consume the event,
        # apply a bounded wheel movement to our own viewport.
        handled = super().on_touch_down(touch)
        if handled:
            return True
        props = getattr(self, "_psx_props", None)
        button = getattr(touch, "button", "")
        if (
            props is None or not props["enabled"] or
            button not in ("scrollup", "scrolldown", "scrollleft", "scrollright") or
            not self.collide_point(*touch.pos)
        ):
            return handled
        horizontal, vertical = scroll_axes(props["direction"])
        is_horizontal = button in ("scrollleft", "scrollright")
        allowed = horizontal if is_horizontal else vertical
        if not allowed:
            return handled
        content = self._psx_content
        extent = (
            content.width - self.width if is_horizontal
            else content.height - self.height
        )
        if extent <= 0:
            return handled
        # Normalized Kivy scroll_x grows right, scroll_y grows up.
        delta = self.scroll_wheel_distance / extent
        if button == "scrollup":
            new_value = min(1.0, self.scroll_y + delta)
            moved = new_value != self.scroll_y
            self.scroll_y = new_value
        elif button == "scrolldown":
            new_value = max(0.0, self.scroll_y - delta)
            moved = new_value != self.scroll_y
            self.scroll_y = new_value
        elif button == "scrollright":
            new_value = min(1.0, self.scroll_x + delta)
            moved = new_value != self.scroll_x
            self.scroll_x = new_value
        else:
            new_value = max(0.0, self.scroll_x - delta)
            moved = new_value != self.scroll_x
            self.scroll_x = new_value
        return True if moved else handled


class KivyScrollAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = scroll_props(node.props)
        view = _PSXScrollView(
            do_scroll_x=True, do_scroll_y=True, size_hint=(1, 1),
            bar_width=6, scroll_type=["bars", "content"],
            scroll_wheel_distance=48, smooth_scroll_end=10,
        )
        content = BoxLayout(
            orientation=props["content_direction"],
            size_hint=(None, None),
        )
        view.add_widget(content)
        view._psx_content = content
        self._apply(view, props)
        self._connect(view)
        return KivyHandle("Scroll", view, props)

    @staticmethod
    def _apply(view, props):
        view._psx_props = props
        x, y = scroll_axes(props["direction"])
        view.do_scroll_x = x and props["enabled"]
        view.do_scroll_y = y and props["enabled"]
        content = view._psx_content
        content.orientation = props["content_direction"]
        content.padding = scroll_padding(props)
        content.spacing = props["spacing"]
        view.size_hint_x = None if props["width"] is not None else 1
        view.size_hint_y = None if props["height"] is not None else 1
        if props["width"] is not None:
            view.width = float(props["width"])
        if props["height"] is not None:
            view.height = float(props["height"])
        view.bar_width = 6 if props["scrollbar"] != "hidden" else 0
        view.bar_color = (0.62, 0.62, 0.62, 0.78) if props["scrollbar"] != "hidden" else (0, 0, 0, 0)
        view.bar_inactive_color = (
            (0.62, 0.62, 0.62, 0.50) if props["scrollbar"] == "always"
            else (0, 0, 0, 0)
        )
        view.scroll_type = ["bars", "content"] if props["scrollbar"] != "hidden" else ["content"]
        view.disabled = not props["enabled"]
        KivyScrollAdapter._resize_content(view)

    @staticmethod
    def _resize_content(view):
        content = view._psx_content
        x, y = scroll_axes(view._psx_props["direction"])
        # Cross-axis sizing clamps to the viewport. The scrollable axis must
        # retain measured minimum dimensions instead of a fill size_hint.
        content.width = max(content.minimum_width, view.width) if x else view.width
        content.height = max(content.minimum_height, view.height) if y else view.height

    @staticmethod
    def _connect(view):
        content = view._psx_content
        view.bind(size=lambda *_: KivyScrollAdapter._resize_content(view))
        content.bind(minimum_size=lambda *_: KivyScrollAdapter._resize_content(view))

    def update(self, renderer, handle, changed, removed):
        props = updated_scroll_props(handle.props, changed, removed)
        position = (handle.widget.scroll_x, handle.widget.scroll_y)
        self._apply(handle.widget, props)
        handle.widget.scroll_x, handle.widget.scroll_y = position
        handle.props = props
        self._layout_children(handle)

    def insert(self, renderer, parent, child, index):
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        self._layout_children(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.children.remove(child)
        parent.children.insert(index, child)
        self._layout_children(parent)
        return True

    def remove(self, renderer, parent, child):
        if child in parent.children:
            parent.children.remove(child)
        content = parent.widget._psx_content
        if child.widget.parent is content:
            content.remove_widget(child.widget)
        if (
            child.native is not None
            and child.native.ownership is NativeOwnership.BORROWED
            and child.original_parent is not None
        ):
            child.original_parent.add_widget(child.widget)
        return True

    @staticmethod
    def _layout_children(handle):
        content = handle.widget._psx_content
        desired = [child.widget for child in reversed(handle.children)]
        # Preserve matching widgets; only reorder where necessary.
        for widget in tuple(content.children):
            if widget not in desired:
                content.remove_widget(widget)
        for i, widget in enumerate(desired):
            if widget.parent is not content:
                content.add_widget(widget, index=i)
            elif content.children.index(widget) != i:
                content.remove_widget(widget)
                content.add_widget(widget, index=i)
        for widget in content.children:
            widget.size_hint_y = None if handle.props["content_direction"] == "vertical" else widget.size_hint_y
            widget.size_hint_x = None if handle.props["content_direction"] == "horizontal" else widget.size_hint_x
        KivyScrollAdapter._resize_content(handle.widget)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Scroll does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        view = handle.widget
        if view.parent is not None:
            view.parent.remove_widget(view)
