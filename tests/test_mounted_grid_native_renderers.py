"""Executable mounted Grid lifecycle against each native renderer (not metadata-only)."""
from __future__ import annotations

import importlib
import os

import pytest

from psx import Grid, GridItem, Text
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


def viewport(width):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(200, True))


def view(order=("a", "b")):
    return Grid(*(GridItem(Text(key.upper(), key="leaf"), key=key,
                           span={"base": 12, "md": 6})
                  for key in order), gap=4)


def make_renderer(backend):
    if backend == "qt":
        binding = os.environ["PSX_QT_BINDING"]
        package = {"pyside6": "PySide6", "pyside2": "PySide2",
                   "pyqt5": "PyQt5", "pyqt6": "PyQt6"}[binding]
        namespace = "pyside" if binding.startswith("pyside") else "pyqt"
        facade = importlib.import_module("psx.renderers.qt." + namespace)
        renderer = getattr(facade, package + "Renderer")(
            argv=["psx-grid-lifecycle"], sfle_constraints=viewport(800),
            engine=PythonLayoutEngine())
        return renderer, lambda: renderer.application.processEvents()
    if backend == "tk":
        import tkinter as tk
        from psx.renderers.tkinter import TkinterRenderer
        root = tk.Tk()
        root.withdraw()
        renderer = TkinterRenderer(root=root, sfle_constraints=viewport(800),
                                   engine=PythonLayoutEngine())
        return renderer, root.destroy
    if backend == "kivy":
        from psx.renderers.kivy.kivy import KivyRenderer
        return KivyRenderer(sfle_constraints=viewport(800),
                            engine=PythonLayoutEngine()), lambda: None
    raise AssertionError("PSX_GRID_BACKEND must name a real native backend")


def rectangle(widget, backend):
    if backend == "qt":
        r = widget.geometry()
        return (r.x(), r.y(), r.width(), r.height())
    if backend == "tk":
        d = widget.place_info()
        return tuple(float(d[k]) for k in ("x", "y", "width", "height"))
    return (*widget.pos, *widget.size)


def test_mounted_grid_native_parentage_reflow_keyed_reorder_and_teardown():
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(view())
        assert renderer.grid_result is not None
        a, b = root.children
        aw, bw = a.handle.widget, b.handle.widget
        al, bl = a.children[0].handle.widget, b.children[0].handle.widget
        assert a.handle.widget is not b.handle.widget
        if backend == "qt":
            assert aw.parentWidget() is root.handle.widget
            assert al.parentWidget() is aw
        elif backend == "tk":
            assert aw.winfo_parent() == str(root.handle.widget)
            assert al.winfo_parent() == str(aw)
        else:
            assert aw.parent is root.handle.widget
            assert al.parent is aw
        assert rectangle(aw, backend)[2] == pytest.approx(398, abs=1)
        assert rectangle(bw, backend)[2] == pytest.approx(398, abs=1)
        assert rectangle(al, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(root)
        assert rectangle(aw, backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        reordered = reconciler.render(view(("b", "a")))
        assert reordered.children[0].handle.widget is bw
        assert reordered.children[1].handle.widget is aw
        assert reordered.children[0].children[0].handle.widget is bl
        assert reordered.children[1].children[0].handle.widget is al
        assert renderer.grid_result[1].max_readback_error <= 1
    finally:
        reconciler.unmount()
        close()
