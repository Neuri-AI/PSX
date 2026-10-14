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
        a_widget = first.children[0].handle.widget
        renderer.set_sfle_constraints(viewport(767))
        # Kivy may synchronously resize the viewport host on constraint update;
        # rollback is defined against the geometry at commit entry.
        before = rectangle(parent_widget, backend)
        child_before = rectangle(a_widget, backend)

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
        assert getattr(renderer, "grid_result", None) is None
        assert_feature(request, Feature("Grid", binding, "interaction",
                                        "nested_container", "fails_closed",
                                        applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


def test_component_boundaries_participate_in_native_grid(request):
    """The reconciler, not Cinnamon, evaluates component roots and preserves handles."""
    from psx import component
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")

    @component
    def Leaf(value: str):
        return Text(value)

    @component
    def Screen(value: str):
        return Grid(
            GridItem(Leaf(value=value), span={"base": 12, "md": 6}, key="left"),
            GridItem(Text("right"), span={"base": 12, "md": 6}, key="right"),
            gap=4,
        )

    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        mounted = tree.render(Screen(value="original"))
        grid = mounted.children[0]
        item = grid.children[0]
        leaf = item.children[0].children[0]
        original_widget = leaf.handle.widget
        assert rectangle(item.handle.widget, backend)[2] == pytest.approx(398, abs=1)
        assert rectangle(original_widget, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1

        changed = tree.render(Screen(value="updated"))
        assert changed.children[0].children[0].children[0].children[0].handle.widget is original_widget
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "GridItem", binding, "interaction", "component_boundary",
            "keyed_update_readback", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


def test_composite_grid_item_fails_closed_without_false_native_receipt(request):
    """G4 composite measurement must not be guessed or delegated to toolkits."""
    from psx import Flex
    from psx.sfle.grid_math import GridPackingError
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        with pytest.raises(GridPackingError, match="Composite GridItem measurement"):
            tree.render(Grid(GridItem(Flex(Text("a"), Text("b")))))
        assert getattr(renderer, "grid_result", None) is None
        assert_feature(request, Feature(
            "GridItem", binding, "interaction", "composite_content",
            "fails_closed", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


@pytest.mark.parametrize("width,expected", [
    (767, 767),
    (800, 398),
])
def test_grid_responsive_threshold_cycle_preserves_native_identity(
    request, width, expected,
):
    """Every crossing re-evaluates Grid's own content width without remount."""
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(view())
        first = root.children[0].handle.widget
        second = root.children[1].handle.widget
        first_leaf = root.children[0].children[0].handle.widget
        second_leaf = root.children[1].children[0].handle.widget
        for target in (width, 800 if width == 767 else 767, width):
            renderer.set_sfle_constraints(viewport(target))
            renderer.commit_layout(root)
        assert rectangle(first, backend)[2] == pytest.approx(expected, abs=1)
        assert rectangle(second, backend)[2] == pytest.approx(expected, abs=1)
        assert root.children[0].handle.widget is first
        assert root.children[1].handle.widget is second
        assert root.children[0].children[0].handle.widget is first_leaf
        assert root.children[1].children[0].handle.widget is second_leaf
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "responsive_cycle",
            f"width_{width}_{expected}", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


def nested_view():
    return Grid(
        GridItem(
            Grid(
                GridItem(Text("inner A"), key="inner-a",
                         span={"base": 12, "md": 6}),
                GridItem(Text("inner B"), key="inner-b",
                         span={"base": 12, "md": 6}),
                gap=4,
            ),
            key="outer-a", span={"base": 12, "md": 6},
        ),
        GridItem(Text("outer B"), key="outer-b",
                 span={"base": 12, "md": 6}),
        gap=4,
    )


def test_nested_grid_reflows_at_independent_content_width(request):
    """A nested Grid crosses md when its own content box does, not the window."""
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(nested_view())
        outer = root.children[0]
        nested_grid = outer.children[0]
        inner_a, inner_b = nested_grid.children
        first_widget = inner_a.handle.widget
        second_widget = inner_b.handle.widget
        first_leaf = inner_a.children[0].handle.widget
        assert rectangle(outer.handle.widget, backend)[2] == pytest.approx(398, abs=1)
        assert rectangle(first_widget, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1

        renderer.set_sfle_constraints(viewport(1600))
        renderer.commit_layout(root)
        assert rectangle(outer.handle.widget, backend)[2] == pytest.approx(798, abs=1)
        assert rectangle(first_widget, backend)[2] == pytest.approx(397, abs=1)
        assert rectangle(second_widget, backend)[2] == pytest.approx(397, abs=1)
        assert inner_a.handle.widget is first_widget
        assert inner_b.handle.widget is second_widget
        assert inner_a.children[0].handle.widget is first_leaf
        assert renderer.grid_result[1].max_readback_error <= 1

        renderer.set_sfle_constraints(viewport(800))
        renderer.commit_layout(root)
        assert rectangle(first_widget, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "nested_content_width",
            "independent_breakpoint_reflow", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


def test_nested_grid_honors_application_custom_breakpoints(request):
    """Configured md applies to each Grid's local content width, not the viewport."""
    from psx.app import App
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    thresholds = {"base": 0, "sm": 100, "md": 350, "lg": 700, "xl": 900}
    renderer, close = make_renderer(backend)
    application = App(
        nested_view(), renderer=renderer,
        settings={"grid": {"breakpoints": thresholds}},
    )
    try:
        root = application.reconciler.render(application.root)
        nested_grid = root.children[0].children[0]
        inner = nested_grid.children[0].handle.widget
        assert rectangle(inner, backend)[2] == pytest.approx(197, abs=1)
        renderer.set_sfle_constraints(viewport(600))
        renderer.commit_layout(root)
        # The outer Grid still splits at the custom md=350, but its nested
        # Grid receives only a 298px content box and must now stack.
        assert rectangle(root.children[0].handle.widget, backend)[2] == pytest.approx(298, abs=1)
        assert rectangle(inner, backend)[2] == pytest.approx(298, abs=1)
        assert inner is nested_grid.children[0].handle.widget
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "configured_container_breakpoints",
            "isolated_nested_resolution", applicability="partial_native"), True)
    finally:
        application.unmount()
        close()
