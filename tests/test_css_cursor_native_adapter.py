"""Real native cursor projections for CSS on Qt, Tk and Kivy."""

import os

import pytest

from psx import psx
from psx.css.cursor import QT_CURSOR_SHAPES, TK_CURSOR_SHAPES
from psx.core.reconcile import Reconciler
from tests.test_mounted_grid_native_renderers import make_renderer


@pytest.mark.parametrize("value", (
    "default", "none", "context-menu", "help",
    "pointer", "progress", "wait",
))
def test_css_cursor_on_native_button_and_container(value):
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        root = tree.render(psx(
            '<div style="cursor:' + value + '">'
            '<button style="cursor:' + value + '">Click</button></div>'
        ))
        for node in (root, root.children[0]):
            widget = node.handle.widget
            if backend == "qt":
                cursor_enum = renderer._qtcore.Qt
                shapes = getattr(cursor_enum, "CursorShape", cursor_enum)
                assert widget.cursor().shape() == getattr(shapes, QT_CURSOR_SHAPES[value])
            elif backend == "tk":
                assert str(widget.cget("cursor")) in (
                    TK_CURSOR_SHAPES[value], "arrow"
                )
            else:
                assert renderer._psx_css_cursor_manager.styles[widget] == value
        cleared = tree.render(psx(
            "<div><button>Click</button></div>"
        ))
        assert cleared.handle.widget is root.handle.widget
        if backend == "kivy":
            manager = renderer._psx_css_cursor_manager
            assert not manager.styles
    finally:
        tree.unmount()
        close()
