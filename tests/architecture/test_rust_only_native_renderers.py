"""Real native UI certification with the complete Python solver directory removed.

Invoke each test in its own xvfb-run process after a compiled Rust wheel has
been installed. The fixtures intentionally use the *same* markup and CSS on
Qt, Tk and Kivy so a renderer silently importing fallback fails immediately.
"""
from __future__ import annotations

import sys

from psx import psx
from psx.core.reconcile import Reconciler
from psx.layout.contracts.model import AvailableSize, LayoutConstraints

MARKUP = (
    '<div style="display:block">'
    '<p>Edit <span>main.py</span> and save to test HMR</p>'
    '<button>Count is 0</button>'
    '</div>'
)


def _viewport():
    return LayoutConstraints(AvailableSize(480, True),
                             AvailableSize(300, True))


def _assert_clean(renderer, root):
    assert renderer._sfle_engine.backend_name == "rust"
    assert renderer.sfle_result is not None
    assert renderer.sfle_result.geometry_commit_error is None or (
        renderer.sfle_result.geometry_commit_error <= 1.0
    )
    assert len(root.children) == 2
    assert root.children[0].node.type == "p"
    assert root.children[1].node.type in ("Button", "button")
    assert not [key for key in sys.modules
                if key.startswith("psx.layout.fallback")]


def test_qt_actual_rust_only_paragraph_and_button():
    from psx.renderers.qt.pyside import PySide6Renderer
    renderer = PySide6Renderer(
        argv=["cinnamon-rust-only-qt"], sfle_constraints=_viewport(),
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(MARKUP))
        _assert_clean(renderer, root)
        button = root.children[1].handle.widget
        assert button.width() >= 40
        renderer.set_sfle_constraints(
            LayoutConstraints(AvailableSize(350, True), AvailableSize(300, True))
        )
        renderer.commit_layout(root)
        assert button.width() >= 40
        _assert_clean(renderer, root)
    finally:
        reconciler.unmount()
        renderer.application.processEvents()


def test_tk_actual_rust_only_paragraph_and_button():
    import tkinter as tk
    from psx.renderers.tkinter.tkinter import TkinterRenderer
    host = tk.Tk()
    host.geometry("500x350+0+0")
    host.update_idletasks()
    renderer = TkinterRenderer(root=host, sfle_constraints=_viewport())
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(MARKUP))
        host.update_idletasks()
        _assert_clean(renderer, root)
        button = root.children[1].handle.widget
        width = int(float(button.place_info()["width"]))
        assert width >= 40
        renderer.set_sfle_constraints(
            LayoutConstraints(AvailableSize(350, True), AvailableSize(300, True))
        )
        renderer.commit_layout(root)
        _assert_clean(renderer, root)
    finally:
        reconciler.unmount()
        renderer.close()
        host.destroy()


def test_kivy_actual_rust_only_paragraph_and_button():
    from kivy.config import Config
    Config.set("graphics", "window_state", "hidden")
    from psx.renderers.kivy.kivy import KivyRenderer
    renderer = KivyRenderer(sfle_constraints=_viewport())
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(MARKUP))
        _assert_clean(renderer, root)
        button = root.children[1].handle.widget
        assert button.width >= 40
        renderer.set_sfle_constraints(
            LayoutConstraints(AvailableSize(350, True), AvailableSize(300, True))
        )
        renderer.commit_layout(root)
        assert button.width >= 40
        _assert_clean(renderer, root)
    finally:
        reconciler.unmount()
