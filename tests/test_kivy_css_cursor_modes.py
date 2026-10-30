from psx.renderers.kivy.css_cursor import KivyCssCursorManager


class Window:
    def __init__(self):
        self.mouse_pos = (0, 0)
        self.show_cursor = True
        self.children = []
        self.events = {}
        self.cursor = "arrow"

    def bind(self, **kw):
        self.events.update(kw)

    def unbind(self, **kw):
        for key in kw:
            self.events.pop(key)

    def set_system_cursor(self, name):
        self.cursor = name


class Widget:
    def __init__(self, parent):
        self.parent = parent
        self.width = 100
        self.height = 100
        self.opacity = 1
        self.disabled = False
        parent.children.append(self)

    def to_widget(self, x, y):
        return x, y


def test_css_none_hides_cursor_and_restores_on_leave():
    window = Window()
    widget = Widget(window)
    manager = KivyCssCursorManager(window)
    manager.set_style(widget, "none")
    manager.update((10, 10))
    assert window.show_cursor is False
    manager.update((200, 200))
    assert window.show_cursor is True
    manager.close()
    assert not window.events


def test_kivy_keyword_shapes_are_applied_on_hover():
    from psx.css.cursor import KIVY_CURSOR_SHAPES
    window = Window()
    widget = Widget(window)
    manager = KivyCssCursorManager(window)
    for css, name in KIVY_CURSOR_SHAPES.items():
        manager.set_style(widget, css)
        manager.update((10, 10))
        assert window.cursor == name
        assert window.show_cursor == (css != "none")
    manager.close()
