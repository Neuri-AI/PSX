"""Executable mounted Grid lifecycle against each native renderer (not metadata-only)."""
from __future__ import annotations

import importlib
import os

import pytest

from psx import Grid, GridItem, Text
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature


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


def test_mounted_grid_native_parentage_reflow_keyed_reorder_and_teardown(request):
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    def receipt(component, name, scenario):
        assert_feature(request, Feature(component, binding, "interaction", name,
                                        scenario, applicability="partial_native"), True)
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
        receipt("Grid", "native_root", "geometry_readback")
        receipt("GridItem", "native_child", "geometry_readback")
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(root)
        assert rectangle(aw, backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        receipt("Grid", "native_root", "resize_reflow")
        reordered = reconciler.render(view(("b", "a")))
        assert reordered.children[0].handle.widget is bw
        assert reordered.children[1].handle.widget is aw
        assert reordered.children[0].children[0].handle.widget is bl
        assert reordered.children[1].children[0].handle.widget is al
        assert renderer.grid_result[1].max_readback_error <= 1
        receipt("Grid", "native_root", "keyed_reorder")
    finally:
        reconciler.unmount()
        assert reconciler.root is None
        close()
    receipt("Grid", "native_root", "teardown")


def test_grid_root_geometry_is_restored_when_native_batch_fails(request, monkeypatch):
    """A rejected native commit must not leave the resized root behind."""
    from psx.sfle import native_grid_bridge
    from psx.sfle.errors import SFLEError

    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        first = tree.render(view())
        parent_widget = first.handle.widget
        before = rectangle(parent_widget, backend)
        a_widget = first.children[0].handle.widget
        child_before = rectangle(a_widget, backend)
        renderer.set_sfle_constraints(viewport(767))

        def fail_commit(*args, **kwargs):
            raise RuntimeError("simulated native commit rejection")

        with monkeypatch.context() as patch:
            patch.setattr(native_grid_bridge, "commit_grid_native_geometry", fail_commit)
            with pytest.raises(RuntimeError, match="simulated native commit rejection"):
                renderer.commit_layout(first)
        assert rectangle(parent_widget, backend) == pytest.approx(before, abs=1)
        assert rectangle(a_widget, backend) == pytest.approx(child_before, abs=1)
        renderer.commit_layout(first)
        assert rectangle(parent_widget, backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(
            request, Feature("Grid", binding, "interaction", "native_root",
                             "failed_commit_root_rollback", applicability="partial_native"),
            True,
        )
    finally:
        tree.unmount()
        close()


def test_grid_under_flex_fails_closed_without_fallback(request):
    """G4 nested integration is intentionally not enabled by a native layout."""
    from psx import Flex
    from psx.core.errors import RendererCapabilityError

    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        with pytest.raises(RendererCapabilityError, match="Nested Grid"):
            tree.render(Flex(view(), width="800px", height="200px"))
        assert renderer.grid_result is None
        assert_feature(request, Feature("Grid", binding, "interaction",
                                        "nested_container", "fails_closed",
                                        applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()
