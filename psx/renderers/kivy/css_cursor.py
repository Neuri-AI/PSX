"""Renderer-owned CSS cursor hover for Kivy's single SDL window.

Unlike Qt and Tk widgets, Kivy children do not own an OS cursor. A single
Window mouse_pos listener resolves CSS cursor styles over the native tree.
The registry has weak widget keys; no per-widget Window subscriptions remain
after style removal or renderer teardown.
"""
from __future__ import annotations

from weakref import WeakKeyDictionary

from psx.css.cursor import KIVY_CURSOR_SHAPES


class KivyCssCursorManager:
    def __init__(self, window: object):
        self.window = window
        self.styles: WeakKeyDictionary = WeakKeyDictionary()
        self._bound = False
        self._current = "arrow"
        self._visible = getattr(window, "show_cursor", True)

    def set_style(self, widget: object, value: str | None) -> None:
        if value in KIVY_CURSOR_SHAPES:
            self.styles[widget] = value
            if not self._bound:
                self.window.bind(
                    mouse_pos=self._on_mouse_pos,
                    on_cursor_leave=self._on_cursor_leave,
                    on_cursor_enter=self._on_cursor_enter,
                )
                self._bound = True
        else:
            self.styles.pop(widget, None)
        if not self.styles:
            self.close()
        else:
            self.update(self.window.mouse_pos)

    def _rank(self, widget: object) -> tuple[int, ...] | None:
        """Visual stacking path: Kivy children[0] is painted on top."""
        path = []
        current = widget
        while current is not self.window:
            parent = getattr(current, "parent", None)
            if parent is None:
                return None
            try:
                path.append(-parent.children.index(current))
            except (AttributeError, ValueError):
                return None
            current = parent
        return tuple(reversed(path))

    @staticmethod
    def _contains(widget: object, point: tuple[float, float]) -> bool:
        if not getattr(widget, "opacity", 1) or getattr(widget, "disabled", False):
            return False
        x, y = widget.to_widget(*point)
        if not (0 <= x < widget.width and 0 <= y < widget.height):
            return False
        # Scroll's canvas transformation can leave a descendant's native
        # bounds under the mouse even when the viewport clips it. Never
        # advertise a pointer outside the visible clipping rectangle.
        parent = getattr(widget, "parent", None)
        while parent is not None:
            if not getattr(parent, "opacity", 1):
                return False
            if hasattr(parent, "_psx_content"):
                x, y = parent.to_widget(*point)
                if not (0 <= x < parent.width and 0 <= y < parent.height):
                    return False
            parent = getattr(parent, "parent", None)
        return True

    def update(self, point: tuple[float, float]) -> None:
        selected = None
        selected_rank = ()
        for widget, cursor in tuple(self.styles.items()):
            rank = self._rank(widget)
            if rank is None or not self._contains(widget, point):
                continue
            if selected is None or rank > selected_rank:
                selected, selected_rank = cursor, rank
        self._set_cursor(selected)

    def _set_cursor(self, value: str | None) -> None:
        # Kivy's SDL 'no' may fall back to IBeam under Wayland. Use the
        # Window visibility property for CSS none instead.
        visible = value != "none"
        if visible != self._visible:
            self.window.show_cursor = visible
            self._visible = visible
        cursor = KIVY_CURSOR_SHAPES.get(value, "arrow")
        if cursor != self._current:
            self.window.set_system_cursor(cursor)
            self._current = cursor

    def _on_mouse_pos(self, _window: object, point: tuple[float, float]) -> None:
        self.update(point)

    def _on_cursor_leave(self, *_args: object) -> None:
        self._set_cursor("arrow")

    def _on_cursor_enter(self, *_args: object) -> None:
        self.update(self.window.mouse_pos)

    def close(self) -> None:
        if self._bound:
            self.window.unbind(
                mouse_pos=self._on_mouse_pos,
                on_cursor_leave=self._on_cursor_leave,
                on_cursor_enter=self._on_cursor_enter,
            )
            self._bound = False
        self.styles.clear()
        self._set_cursor("arrow")
