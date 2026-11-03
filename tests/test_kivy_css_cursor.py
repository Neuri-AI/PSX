"""CSS cursor pointer/default hover, ownership, and live style restoration."""

from __future__ import annotations

from psx.renderers.kivy.css_cursor import KivyCssCursorManager


class Window:
    def __init__(self):
        self.children = []
        self.mouse_pos = (0, 0)
        self.bindings = {}
        self.cursors = []

    def bind(self, **kwargs):
        self.bindings.update(kwargs)

    def unbind(self, **kwargs):
        for name, callback in kwargs.items():
            assert self.bindings.pop(name) == callback

    def set_system_cursor(self, name):
        self.cursors.append(name)

    def emit(self, name, value=None):
        if name == "mouse_pos":
            self.mouse_pos = value
            self.bindings[name](self, value)
        else:
            self.bindings[name](self)


class Widget:
    def __init__(self, parent, rect, *, opacity=1, disabled=False):
        self.parent = parent
        self.x, self.y, self.width, self.height = rect
        self.opacity = opacity
        self.disabled = disabled
        self.children = []
        parent.children.insert(0, self)

    def to_widget(self, x, y):
        node = self
        while isinstance(node, Widget):
            x -= node.x
            y -= node.y
            node = node.parent
        return x, y


def test_css_pointer_hover_style_change_and_unmount_restore_arrow():
    window = Window()
    button = Widget(window, (10, 10, 80, 30))
    manager = KivyCssCursorManager(window)
    manager.set_style(button, "pointer")
    assert set(window.bindings) == {
        "mouse_pos", "on_cursor_leave", "on_cursor_enter"
    }
    window.emit("mouse_pos", (30, 20))
    assert window.cursors == ["hand"]
    window.emit("mouse_pos", (31, 21))
    assert window.cursors == ["hand"]  # no repeated OS calls
    window.emit("on_cursor_leave")
    assert window.cursors[-1] == "arrow"
    window.emit("on_cursor_enter")
    assert window.cursors[-1] == "hand"

    manager.set_style(button, "default")
    assert window.cursors[-1] == "arrow"
    manager.set_style(button, "pointer")
    assert window.cursors[-1] == "hand"
    manager.set_style(button, None)
    assert window.cursors[-1] == "arrow"
    assert not window.bindings and not manager.styles


def test_deepest_styled_element_wins_and_sibling_hover_is_correct():
    window = Window()
    container = Widget(window, (0, 0, 200, 200))
    nested = Widget(container, (20, 20, 40, 40))
    sibling = Widget(window, (200, 0, 100, 100))
    manager = KivyCssCursorManager(window)
    manager.set_style(container, "pointer")
    manager.set_style(nested, "default")
    manager.set_style(sibling, "pointer")
    window.emit("mouse_pos", (30, 30))
    assert window.cursors[-1] == "arrow"
    window.emit("mouse_pos", (150, 150))
    assert window.cursors[-1] == "hand"
    window.emit("mouse_pos", (250, 50))
    assert window.cursors[-1] == "hand"
    window.emit("mouse_pos", (350, 250))
    assert window.cursors[-1] == "arrow"
    manager.close()
    assert not window.bindings


def test_invisible_or_unmounted_widget_cannot_control_window_cursor():
    window = Window()
    transparent = Widget(window, (0, 0, 80, 80), opacity=0)
    disabled = Widget(window, (90, 0, 80, 80), disabled=True)
    widget = Widget(window, (180, 0, 80, 80))
    manager = KivyCssCursorManager(window)
    for target in (transparent, disabled, widget):
        manager.set_style(target, "pointer")
    window.emit("mouse_pos", (15, 15))
    assert window.cursors == []
    window.emit("mouse_pos", (100, 15))
    assert window.cursors == []
    window.emit("mouse_pos", (200, 15))
    assert window.cursors == ["hand"]
    window.children.remove(widget)
    widget.parent = None
    manager.update((200, 15))
    assert window.cursors[-1] == "arrow"
    manager.close()
    assert not window.bindings



def test_pointer_inside_scrolled_content_stays_within_visible_viewport():
    window = Window()
    viewport = Widget(window, (0, 0, 100, 60))
    viewport._psx_content = object()  # Kivy Scroll ownership marker
    content = Widget(viewport, (0, 0, 100, 180))
    button = Widget(content, (10, 80, 40, 40))
    manager = KivyCssCursorManager(window)
    manager.set_style(button, "pointer")
    # Inside Button's native coordinates, but outside the visible viewport.
    window.emit("mouse_pos", (20, 90))
    assert window.cursors == []
    button.y = 10
    window.emit("mouse_pos", (20, 20))
    assert window.cursors[-1] == "hand"
    manager.close()
    assert window.cursors[-1] == "arrow"
