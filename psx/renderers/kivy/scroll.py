"""Kivy ScrollView with managed multi-child content and overlay indicators."""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView

from psx.core.errors import RendererCapabilityError
from psx.core.native import NativeOwnership
from psx.renderers.components.scroll import (
    scroll_axes, scroll_padding, scroll_props, updated_scroll_props,
)


class _PSXScrollView(ScrollView):
    """Native Kivy scroll input and boundary handling.

    Avoid overriding on_scroll_start: Kivy uses scrollup/scrolldown in its
    effect-coordinate convention, and pre-filtering based on scroll_y can
    block wheel/trackpad events even when content can move.
    """

    def _psx_scroll_delta(self, dx, dy):
        """Apply logical movement once and chain only the unconsumed delta."""
        from psx.renderers.components.scroll import consume_scroll
        remainder_x, remainder_y = float(dx), float(dy)
        props = getattr(self, "_psx_props", None)
        content = getattr(self, "_psx_content", None)
        if props is not None and props["enabled"] and content is not None:
            allow_x, allow_y = scroll_axes(props["direction"])
            max_x = max(0.0, content.width - self.width)
            max_y = max(0.0, content.height - self.height)
            if allow_x and max_x and remainder_x:
                position, remainder_x = consume_scroll(
                    self.scroll_x * max_x, max_x, remainder_x,
                )
                self.scroll_x = position / max_x
            if allow_y and max_y and remainder_y:
                position, remainder_y = consume_scroll(
                    (1.0 - self.scroll_y) * max_y, max_y, remainder_y,
                )
                self.scroll_y = 1.0 - position / max_y
        if remainder_x or remainder_y:
            parent = self.parent
            while parent is not None:
                if hasattr(parent, "_psx_scroll_delta"):
                    return parent._psx_scroll_delta(remainder_x, remainder_y)
                parent = parent.parent
        return remainder_x, remainder_y

    def on_scroll_move(self, touch):
        """Let Kivy own touch kinetics; chain only motion beyond an edge."""
        from psx.renderers.components.scroll import consume_scroll
        props = getattr(self, "_psx_props", None)
        content = getattr(self, "_psx_content", None)
        if not (getattr(self, "_psx_sfle_scroll", False)
                and props and props["enabled"] and content is not None):
            return super().on_scroll_move(touch)
        max_x = max(0.0, content.width - self.width)
        max_y = max(0.0, content.height - self.height)
        start_x = self.scroll_x * max_x
        start_y = (1.0 - self.scroll_y) * max_y
        native_handled = super().on_scroll_move(touch)
        # Screen motion points in the opposite direction to content travel.
        dx = -float(getattr(touch, "dx", 0.0))
        dy = -float(getattr(touch, "dy", 0.0))
        allow_x, allow_y = scroll_axes(props["direction"])
        remainder_x, remainder_y = dx, dy
        if allow_x:
            _, remainder_x = consume_scroll(start_x, max_x, dx)
        if allow_y:
            _, remainder_y = consume_scroll(start_y, max_y, dy)
        if remainder_x or remainder_y:
            ancestor = self.parent
            while ancestor is not None:
                if hasattr(ancestor, "_psx_scroll_delta"):
                    tail = ancestor._psx_scroll_delta(remainder_x, remainder_y)
                    if tail != (remainder_x, remainder_y):
                        return True
                    break
                ancestor = ancestor.parent
        return native_handled

    def on_touch_down(self, touch):
        # Wheel input is discrete. Pan/touch gestures remain owned by Kivy's
        # ScrollView, preserving kinetic effects and native touch lifecycle.
        if (getattr(self, "_psx_sfle_scroll", False)
                and getattr(touch, "is_mouse_scrolling", False)
                and self.collide_point(*touch.pos)):
            directions = {
                "scrollup": (0.0, -48.0),
                "scrolldown": (0.0, 48.0),
                "scrollleft": (-48.0, 0.0),
                "scrollright": (48.0, 0.0),
            }
            movement = directions.get(getattr(touch, "button", ""))
            if movement is not None:
                remaining = self._psx_scroll_delta(*movement)
                if remaining != movement:
                    return True
                return False
        return super().on_touch_down(touch)


class KivyScrollAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle

        props = scroll_props(node.props)
        sfle = renderer._sfle_constraints is not None
        view = _PSXScrollView(
            do_scroll_x=True, do_scroll_y=True,
            size_hint=(None, None) if sfle else (1, 1),
            bar_width=6, scroll_type=["bars", "content"],
            scroll_wheel_distance=48,
        )
        content = (
            Widget(size_hint=(None, None)) if sfle else
            BoxLayout(
                orientation=props["content_direction"],
                size_hint=(None, None),
            )
        )
        view._psx_sfle_scroll = sfle
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
        if not view._psx_sfle_scroll:
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
        if not view._psx_sfle_scroll:
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
        if view._psx_sfle_scroll:
            return
        view.bind(size=lambda *_: KivyScrollAdapter._resize_content(view))
        content.bind(minimum_size=lambda *_: KivyScrollAdapter._resize_content(view))

    def update(self, renderer, handle, changed, removed):
        props = updated_scroll_props(handle.props, changed, removed)
        position = (handle.widget.scroll_x, handle.widget.scroll_y)
        self._apply(handle.widget, props)
        handle.widget.scroll_x, handle.widget.scroll_y = position
        handle.props = props
        if not handle.widget._psx_sfle_scroll:
            self._layout_children(handle)

    def insert(self, renderer, parent, child, index):
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        if parent.widget._psx_sfle_scroll:
            content = parent.widget._psx_content
            child.widget.size_hint = (None, None)
            child.widget.pos_hint = {}
            if child.widget.parent is not content:
                content.add_widget(child.widget)
            return True
        self._layout_children(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.children.remove(child)
        parent.children.insert(index, child)
        if not parent.widget._psx_sfle_scroll:
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
