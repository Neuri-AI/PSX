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


def make_renderer(backend, *, sfle=True):
    layout = {"sfle_constraints": viewport(800), "engine": PythonLayoutEngine()} if sfle else {}
    if backend == "qt":
        binding = os.environ["PSX_QT_BINDING"]
        package = {"pyside6": "PySide6", "pyside2": "PySide2",
                   "pyqt5": "PyQt5", "pyqt6": "PyQt6"}[binding]
        namespace = "pyside" if binding.startswith("pyside") else "pyqt"
        facade = importlib.import_module("psx.renderers.qt." + namespace)
        renderer = getattr(facade, package + "Renderer")(
            argv=["psx-grid-lifecycle"], **layout)
        return renderer, lambda: renderer.application.processEvents()
    if backend == "tk":
        import tkinter as tk
        from psx.renderers.tkinter import TkinterRenderer
        root = tk.Tk()
        root.withdraw()
        renderer = TkinterRenderer(root=root, **layout)
        return renderer, root.destroy
    if backend == "kivy":
        from psx.renderers.kivy.kivy import KivyRenderer
        return KivyRenderer(**layout), lambda: None
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


def test_top_level_qt_grid_resize_preserves_window_position():
    """A Grid root must not take ownership of a user-positioned window."""
    if os.environ.get("PSX_GRID_BACKEND") != "qt":
        pytest.skip("Qt-specific top-level window geometry")
    renderer, close = make_renderer("qt")
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(view())
        window = root.handle.widget
        window.move(137, 83)
        renderer.application.processEvents()
        renderer.set_sfle_constraints(viewport(920))
        renderer.commit_layout(root)
        assert (window.x(), window.y()) == (137, 83)
    finally:
        reconciler.unmount()
        close()


def test_grid_item_dynamically_replaced_child_is_mounted():
    """A state-driven GridItem replacement must be attached and laid out."""
    from psx import Button
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        reconciler.render(Grid(GridItem(Text("Home"), span=12)))
        updated = reconciler.render(Grid(GridItem(Button("Projects"), span=12)))
        widget = updated.children[0].children[0].handle.widget
        parent = updated.children[0].handle.widget
        if backend == "qt":
            # Qt needs show() after a late setParent() on a visible Grid.
            assert not widget.isHidden()
        elif backend == "tk":
            # The native Grid commit owns placement for newly mounted children.
            assert widget.winfo_manager() == "place"
        else:
            # Kivy's insertion attaches the newly created child immediately.
            assert widget.parent is parent
    finally:
        reconciler.unmount()
        close()


def test_auto_width_flex_padding_stays_inside_native_grid_item():
    """The shared Grid→Flex snapshot must reserve the padded content box."""
    from psx import Button, Flex

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(
            Grid(
                GridItem(
                    Flex(
                        Text("Navigation", font_size=20),
                        Button("Home"),
                        Button("Projects"),
                        direction="column", padding="16px", gap="12px",
                    ),
                    span=3,
                ),
                GridItem(Text("Main content"), span=9),
                gap="12px",
            )
        )
        sidebar = root.children[0].children[0].handle.widget
        button = root.children[0].children[0].children[1].handle.widget
        _, _, sidebar_width, _ = rectangle(sidebar, backend)
        button_x, _, button_width, _ = rectangle(button, backend)
        assert button_x >= 15
        assert button_x + button_width <= sidebar_width + 1
    finally:
        reconciler.unmount()
        close()


def test_nested_grid_survives_a_tiny_viewport():
    """Live resizes may briefly make declared Grid gaps wider than a track."""
    from psx import Flex

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(
            Grid(
                GridItem(Text("Navigation"), span=4),
                GridItem(
                    Flex(
                        Grid(
                            GridItem(Text("Card 1"), span=4),
                            GridItem(Text("Card 2"), span=4),
                            GridItem(Text("Card 3"), span=4),
                            gap="12px",
                        ),
                        direction="column", padding="16px", gap="12px",
                    ),
                    span=8,
                ),
                gap="12px",
            )
        )
        renderer.set_sfle_constraints(viewport(5))
        renderer.commit_layout(root)
        assert renderer.grid_result is not None
    finally:
        reconciler.unmount()
        close()


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
        # A top-level Qt window retains window-manager geometry; Cinnamon
        # reflows children without changing the user-owned window rectangle.
        target_width = before[2] if backend == "qt" and parent_widget.isWindow() else 767
        assert rectangle(parent_widget, backend)[2] == pytest.approx(target_width, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(
            request, Feature("Grid", binding, "interaction", "native_root",
                             "failed_commit_root_rollback", applicability="partial_native"),
            True,
        )
    finally:
        tree.unmount()
        close()


def test_scroll_rejects_grid_as_its_content_root(request):
    """Scroll requires one supported content box; Grid alone is not a block root."""
    from psx import Scroll
    from psx.core.errors import RendererCapabilityError

    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        with pytest.raises(RendererCapabilityError, match="one Flex or HTML-like block root"):
            tree.render(Scroll(view(), height=200))
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
        from psx import Scroll
        with pytest.raises(GridPackingError, match="GridItem Scroll requires one HTML-like block content root"):
            tree.render(Grid(GridItem(Scroll(Flex(Text("a"), Text("b"))))))
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


def test_flex_grid_native_geometry_and_resize_reconciliation(request):
    """Mounted Flex assigns actual Grid width; Cinnamon Grid owns descendants."""
    from psx import Flex
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(Flex(
            view(), direction="column", width="100%", height=200,
        ))
        grid = mounted.children[0]
        first = grid.children[0].handle.widget
        leaf = grid.children[0].children[0].handle.widget
        assert rectangle(grid.handle.widget, backend)[2] == pytest.approx(800, abs=1)
        assert rectangle(first, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(mounted)
        assert rectangle(grid.handle.widget, backend)[2] == pytest.approx(767, abs=1)
        assert rectangle(first, backend)[2] == pytest.approx(767, abs=1)
        assert grid.children[0].handle.widget is first
        assert grid.children[0].children[0].handle.widget is leaf
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "mixed_flex",
            "allocated_width_reflow", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


def mixed_scroll_scene(content_width="800px"):
    from psx import Flex, Scroll
    return Flex(
        Scroll(
            Flex(
                view(), direction="column", key="content",
                width=content_width, height="240px",
                align_items="stretch",
            ),
            key="viewport", direction="both",
            layout_width="120px", layout_height="80px",
            flex_basis="120px", flex_shrink=0,
        ),
        direction="row", width="800px", height="200px",
        align_items="flex-start",
    )


def native_scroll_offset(scroll, backend):
    if backend == "qt":
        return (float(scroll.horizontalScrollBar().value()),
                float(scroll.verticalScrollBar().value()))
    if backend == "tk":
        return (float(scroll._psx_canvas.canvasx(0)),
                float(scroll._psx_canvas.canvasy(0)))
    max_x = max(0, scroll._psx_content.width - scroll.width)
    max_y = max(0, scroll._psx_content.height - scroll.height)
    return (scroll.scroll_x * max_x, (1 - scroll.scroll_y) * max_y)


def set_native_scroll_offset(scroll, backend, x, y):
    if backend == "qt":
        scroll.horizontalScrollBar().setValue(round(x))
        scroll.verticalScrollBar().setValue(round(y))
    elif backend == "tk":
        scroll._psx_canvas.xview_moveto(x / scroll._psx_scroll_region[2])
        scroll._psx_canvas.yview_moveto(y / scroll._psx_scroll_region[3])
        scroll.update_idletasks()
    else:
        max_x = max(0, scroll._psx_content.width - scroll.width)
        max_y = max(0, scroll._psx_content.height - scroll.height)
        scroll.scroll_x = x / max_x if max_x else 0
        scroll.scroll_y = 1 - y / max_y if max_y else 1


def test_grid_inside_scroll_flex_preserves_native_offsets_and_reflows(request):
    """Scroll keeps clipping and native offsets; Cinnamon owns nested Grid."""
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(mixed_scroll_scene())
        scroll = mounted.children[0].handle.widget
        inner_flex = mounted.children[0].children[0]
        grid = inner_flex.children[0]
        first = grid.children[0].handle.widget
        first_leaf = grid.children[0].children[0].handle.widget
        assert rectangle(grid.handle.widget, backend)[2] == pytest.approx(800, abs=1)
        assert rectangle(first, backend)[2] == pytest.approx(398, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        set_native_scroll_offset(scroll, backend, 32, 24)
        before = native_scroll_offset(scroll, backend)
        assert before[0] > 0 and before[1] > 0
        renderer.commit_layout(mounted)
        assert native_scroll_offset(scroll, backend) == pytest.approx(before, abs=2)
        assert renderer.grid_result[1].max_readback_error <= 1
        changed = reconciler.render(mixed_scroll_scene("600px"))
        grid_new = changed.children[0].children[0].children[0]
        assert grid_new.children[0].handle.widget is first
        assert grid_new.children[0].children[0].handle.widget is first_leaf
        assert rectangle(grid_new.handle.widget, backend)[2] == pytest.approx(600, abs=1)
        assert rectangle(first, backend)[2] == pytest.approx(600, abs=1)
        assert native_scroll_offset(scroll, backend) == pytest.approx(before, abs=2)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "mixed_scroll",
            "offset_retained_reflow", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


def test_mixed_flex_grid_transaction_failure_restores_all_native_geometry(request, monkeypatch):
    """A failed Grid batch cannot leave an already committed Flex rectangle."""
    from psx import Flex
    from psx.sfle import mixed_grid_native
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        mounted = tree.render(Flex(view(), direction="column", width="100%", height=200))
        grid = mounted.children[0]
        first = grid.children[0].handle.widget
        leaf = grid.children[0].children[0].handle.widget
        renderer.set_sfle_constraints(viewport(767))
        before = (rectangle(grid.handle.widget, backend),
                  rectangle(first, backend), rectangle(leaf, backend))
        with monkeypatch.context() as patch:
            def reject(*args, **kwargs):
                raise RuntimeError("simulated mixed Grid readback failure")
            patch.setattr(mixed_grid_native, "commit_grid_native_geometry", reject)
            with pytest.raises(RuntimeError, match="simulated mixed Grid"):
                renderer.commit_layout(mounted)
        after = (rectangle(grid.handle.widget, backend),
                 rectangle(first, backend), rectangle(leaf, backend))
        assert all(actual == pytest.approx(expected, abs=1)
                   for actual, expected in zip(after, before))
        renderer.commit_layout(mounted)
        assert rectangle(first, backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "mixed_transaction",
            "rollback_and_recovery", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


def test_grid_item_flex_content_uses_cinnamon_native_geometry(request):
    """GridItem can host a measured multi-leaf Flex without a toolkit layout."""
    from psx import Flex
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def scene():
        return Grid(
            GridItem(
                Flex(
                    Text("one", key="one", layout_width="80px", layout_height="20px",
                         flex_basis="80px", flex_shrink=0),
                    Text("two", key="two", layout_width="80px", layout_height="20px",
                         flex_basis="80px", flex_shrink=0),
                    direction="row", width="100%", height="50px",
                    align_items="flex-start", gap=4,
                ),
                key="flex", span=12,
            ),
            gap=4,
        )
    try:
        root = reconciler.render(scene())
        item = root.children[0]
        flex = item.children[0]
        left, right = flex.children
        left_widget, right_widget = left.handle.widget, right.handle.widget
        assert rectangle(flex.handle.widget, backend)[2] == pytest.approx(800, abs=1)
        assert rectangle(left_widget, backend)[2] == pytest.approx(80, abs=1)
        assert rectangle(right_widget, backend)[0] > rectangle(left_widget, backend)[0]
        assert renderer.grid_result[1].max_readback_error <= 1
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(root)
        assert rectangle(flex.handle.widget, backend)[2] == pytest.approx(767, abs=1)
        assert rectangle(left_widget, backend)[2] == pytest.approx(80, abs=1)
        assert flex.children[0].handle.widget is left_widget
        assert flex.children[1].handle.widget is right_widget
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "GridItem", binding, "interaction", "flex_content",
            "measured_children_readback", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


def test_alternating_grid_flex_grid_recurses_without_oscillation(request):
    """A GridItem Flex may contain a second Grid with its own breakpoint."""
    from psx import Flex
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)

    def scene():
        return Grid(
            GridItem(
                Flex(
                    Grid(
                        GridItem(Text("inner one"), span={"base": 12, "md": 6}, key="one"),
                        GridItem(Text("inner two"), span={"base": 12, "md": 6}, key="two"),
                        gap=4, key="nested",
                    ),
                    direction="column", width="100%", height="80px",
                    align_items="stretch",
                ), key="outer", span=12,
            ), gap=4,
        )
    try:
        root = tree.render(scene())
        flex = root.children[0].children[0]
        inner = flex.children[0]
        left = inner.children[0].handle.widget
        right = inner.children[1].handle.widget
        assert rectangle(left, backend)[2] == pytest.approx(398, abs=1)
        assert rectangle(right, backend)[2] == pytest.approx(398, abs=1)
        for width, expected in ((767, 767), (800, 398), (767, 767)):
            renderer.set_sfle_constraints(viewport(width))
            renderer.commit_layout(root)
            assert rectangle(inner.handle.widget, backend)[2] == pytest.approx(width, abs=1)
            assert rectangle(left, backend)[2] == pytest.approx(expected, abs=1)
            assert inner.children[0].handle.widget is left
            assert inner.children[1].handle.widget is right
            assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "alternating_composition",
            "bounded_reflow_identity", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


def test_keyed_flex_grid_siblings_reorder_without_native_remount(request):
    """Multiple Grid roots in one Flex retain their own keyed native subtrees."""
    from psx import Flex
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def scene(order=("first", "second")):
        return Flex(*(
            Grid(
                GridItem(Text(label, key="leaf"), span=12, key="item"),
                key=label, gap=4,
            )
            for label in order
        ), direction="column", width="100%", height=200,
            align_items="stretch")

    try:
        first = reconciler.render(scene())
        saved = {
            node.node.key: (node.handle.widget,
                            node.children[0].handle.widget,
                            node.children[0].children[0].handle.widget)
            for node in first.children
        }
        swapped = reconciler.render(scene(("second", "first")))
        for node in swapped.children:
            assert (node.handle.widget, node.children[0].handle.widget,
                    node.children[0].children[0].handle.widget) == saved[node.node.key]
            assert rectangle(node.children[0].handle.widget, backend)[2] == pytest.approx(800, abs=1)
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(swapped)
        for node in swapped.children:
            assert (node.handle.widget, node.children[0].handle.widget,
                    node.children[0].children[0].handle.widget) == saved[node.node.key]
            assert rectangle(node.children[0].handle.widget, backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "mixed_keyed_siblings",
            "reorder_identity_readback", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("reason", ("resource", "dpi"))
def test_native_grid_root_late_resource_invalidation_is_atomic(request, monkeypatch, reason):
    """A new resource epoch after child readback rolls the whole Grid back."""
    from psx.sfle import native_grid_bridge
    from psx.sfle.errors import SFLEError
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        root = tree.render(view())
        children = tuple((child.handle.widget, child.children[0].handle.widget)
                         for child in root.children)
        handles = (root.handle.widget,) + tuple(
            widget for pair in children for widget in pair)
        # Native host viewports resize when constraints are set; the atomic
        # transaction starts at commit_layout, not at set_sfle_constraints.
        renderer.set_sfle_constraints(viewport(767))
        previous = tuple(rectangle(widget, backend) for widget in handles)
        original = native_grid_bridge.commit_grid_native_geometry
        with monkeypatch.context() as patch:
            def inject_epoch(*args, **kwargs):
                receipt = original(*args, **kwargs)
                renderer._sfle_measurement_invalidations.request(reason)
                return receipt
            patch.setattr(native_grid_bridge, "commit_grid_native_geometry",
                          inject_epoch)
            with pytest.raises(SFLEError, match="invalidated after native readback"):
                renderer.commit_layout(root)
        current = tuple(rectangle(widget, backend) for widget in handles)
        assert all(actual == pytest.approx(old, abs=1)
                   for actual, old in zip(current, previous)), list(zip(previous, current))
        renderer.commit_layout(root)
        assert rectangle(children[0][0], backend)[2] == pytest.approx(767, abs=1)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "semantic_epoch",
            f"late_{reason}_rollback", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()


def test_multiple_mixed_grids_rollback_all_committed_siblings(request, monkeypatch):
    """A failure in the second Grid batch rolls back the first and Flex."""
    from psx import Flex
    from psx.sfle import mixed_grid_native
    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)

    def scene():
        return Flex(*(
            Grid(GridItem(Text(label), span={"base": 12, "md": 6}, key="one"),
                 GridItem(Text("next"), span={"base": 12, "md": 6}, key="two"),
                 key=label, gap=4)
            for label in ("first", "second")
        ), direction="column", width="100%", height=200, align_items="stretch")

    try:
        mounted = tree.render(scene())
        handles = [mounted.handle.widget]
        for grid in mounted.children:
            handles.append(grid.handle.widget)
            for item in grid.children:
                handles.extend((item.handle.widget, item.children[0].handle.widget))
        renderer.set_sfle_constraints(viewport(767))
        before = tuple(rectangle(widget, backend) for widget in handles)
        implementation = mixed_grid_native.commit_grid_native_geometry
        count = [0]
        with monkeypatch.context() as patch:
            def fail_second(*args, **kwargs):
                count[0] += 1
                if count[0] == 2:
                    raise RuntimeError("second Grid transaction aborted")
                return implementation(*args, **kwargs)
            patch.setattr(mixed_grid_native, "commit_grid_native_geometry", fail_second)
            with pytest.raises(RuntimeError, match="second Grid transaction aborted"):
                renderer.commit_layout(mounted)
        assert count[0] == 2
        after = tuple(rectangle(widget, backend) for widget in handles)
        assert all(actual == pytest.approx(previous, abs=1)
                   for actual, previous in zip(after, before)), list(zip(before, after))
        renderer.commit_layout(mounted)
        assert all(rectangle(grid.children[0].handle.widget, backend)[2]
                   == pytest.approx(767, abs=1) for grid in mounted.children)
        assert renderer.grid_result[1].max_readback_error <= 1
        assert_feature(request, Feature(
            "Grid", binding, "interaction", "mixed_multi_grid",
            "second_batch_atomic_rollback", applicability="partial_native"), True)
    finally:
        tree.unmount()
        close()

def test_native_css_typography_updates_text_without_replacing_widget():
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    def view(size, color):
        leading = '; line-height: ' + str(round(size * 1.5)) + 'px' if backend == "kivy" else ''
        return psx(
            '<div><span key="title" style="font-family: Roboto; font-size: ' + str(size) +
            'px; font-weight: 700; text-align: center; color: ' +
            color + leading + '">Hello</span></div>'
        )

    try:
        first = reconciler.render(view(18, "#123456"))
        text_handle = first.children[0].children[0].handle
        widget = text_handle.widget
        if backend == "qt":
            assert widget.font().pixelSize() == 18
            assert widget.font().family() == "Roboto"
            assert widget.font().bold()
            assert "#123456" in widget.styleSheet()
        elif backend == "tk":
            assert widget._psx_text_font.cget("size") == -18
            # The authored family is only usable when actually installed.
            # Otherwise Tk must paint with the active root's font fallback,
            # not silently pretend that a missing face was loaded.
            from tkinter import font as tkfont
            installed = {name.casefold() for name in tkfont.families(root=widget)}
            expected = ("Roboto" if "roboto" in installed else
                        tkfont.nametofont("TkDefaultFont", root=widget).actual("family"))
            assert widget._psx_text_font.cget("family").casefold() == expected.casefold()
            assert widget._psx_text_font.actual("weight") == "bold"
            assert str(widget.cget("foreground")) == "#123456"
            assert str(widget.cget("justify")) == "center"
        else:
            assert widget.font_size == 18
            assert widget.font_name == "Roboto"
            assert widget.line_height == pytest.approx(1.5)
            assert widget.bold is True
            assert widget.halign == "center"
            assert tuple(widget.color) == pytest.approx((18 / 255, 52 / 255, 86 / 255, 1))
        updated = reconciler.render(view(24, "#654321"))
        assert updated.children[0].children[0].handle.widget is widget
        if backend == "qt":
            assert widget.font().pixelSize() == 24
            assert "#654321" in widget.styleSheet()
        elif backend == "tk":
            assert widget._psx_text_font.cget("size") == -24
            assert str(widget.cget("foreground")) == "#654321"
        else:
            assert widget.font_size == 24
            assert widget.line_height == pytest.approx(1.5)
            assert tuple(widget.color) == pytest.approx((101 / 255, 67 / 255, 33 / 255, 1))
        plain = reconciler.render(psx('<div><span key="title">Hello</span></div>'))
        assert plain.children[0].children[0].handle.widget is widget
        if backend == "qt":
            assert widget.font().pixelSize() == 16
            assert widget.font().bold() is False
            assert widget.styleSheet() == ""
        elif backend == "tk":
            assert widget._psx_text_font.actual("weight") == "normal"
        else:
            assert widget.font_size == 16
            assert widget.line_height == widget.property("line_height").defaultvalue
            assert widget.font_name == widget._psx_css_default_font_name
            assert widget.bold is False
    finally:
        reconciler.unmount()
        close()


def test_native_multiline_css_line_height_follows_cinnamon_measurement():
    """Native line boxes and intrinsic measurements must use one line-height."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    if backend == "kivy":
        pytest.skip("Qt and Tk native line-height certification only")
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    from dataclasses import replace

    def view(leading):
        style = (
            ' style="font-size: 16px; line-height: ' + str(leading) + 'px"'
            if leading is not None else ""
        )
        root = psx("<div><span" + style + "></span></div>")
        span = root.children[0]
        content = Text("Several words here should wrap over multiple lines", key="text")
        content = replace(content, css_computed=span.css_computed)
        return replace(root, children=(replace(span, children=(content,)),))

    try:
        first = reconciler.render(view(32))
        widget = first.children[0].children[0].handle.widget
        if backend == "qt":
            assert widget._psx_css_line_height == 32
            assert widget.heightForWidth(60) >= 64
        else:
            from psx.sfle.tk_measurement import TkMeasurementSource
            assert widget._psx_css_line_height == 32
            assert str(widget.cget("text")) == "Several words here should wrap over multiple lines"
            assert TkMeasurementSource._css_text_metrics(widget, 60).preferred_height >= 64
            assert widget._psx_css_text_layer.winfo_exists()
            gap = 32 - widget._psx_text_font.metrics("linespace")
            assert int(widget._psx_css_text_layer.cget("spacing2")) == gap
            assert int(widget._psx_css_text_layer.cget("spacing3")) == gap
        second = reconciler.render(view(40))
        assert second.children[0].children[0].handle.widget is widget
        if backend == "qt":
            assert widget.heightForWidth(60) >= 80
        else:
            assert TkMeasurementSource._css_text_metrics(widget, 60).preferred_height >= 80
            assert int(widget._psx_css_text_layer.cget("spacing2")) == 40 - widget._psx_text_font.metrics("linespace")
        third = reconciler.render(view(None))
        assert third.children[0].children[0].handle.widget is widget
        assert widget._psx_css_line_height is None
        if backend == "tk":
            assert not hasattr(widget, "_psx_css_text_layer")
    finally:
        reconciler.unmount()
        close()


def test_native_button_css_typography_is_applied_and_reset():
    """CSS typography must style existing Button widgets without replacing them."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        first = reconciler.render(psx(
            '<div><button key="cta" style="font-size: 23px; font-weight: 700; font-family: Roboto; line-height: 36px; text-align: center">Save</button></div>'
        ))
        button = first.children[0].handle.widget
        if backend == "qt":
            assert button._psx_css_line_height == 36
            assert button.font().pixelSize() == 23
            assert button.font().bold()
            assert button.font().family() == "Roboto"
            assert "text-align: center" in button.styleSheet()
        elif backend == "tk":
            assert button._psx_css_native_font.cget("size") == -23
            from tkinter import ttk
            assert ttk.Style(button).lookup(str(button.cget("style")), "padding")
            assert str(ttk.Style(button).lookup(str(button.cget("style")), "anchor")) == "center"
            assert button._psx_css_native_font.actual("weight") == "bold"
        else:
            assert button.font_size == 23
            assert button.line_height == pytest.approx(36 / 23)
            assert button.halign == "center"
            assert button.bold
        second = reconciler.render(psx('<div><button key="cta">Save</button></div>'))
        assert second.children[0].handle.widget is button
        if backend == "qt":
            assert button._psx_css_line_height is None
            assert not button.font().bold()
        elif backend == "tk":
            assert button._psx_css_native_font.actual("weight") == "normal"
        else:
            assert not button.bold
    finally:
        reconciler.unmount()
        close()


def test_native_input_css_inherits_font_and_alignment_without_remount():
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(size):
        return psx(
            '<div style="font-size: ' + str(size) +
            'px; font-family: Roboto"><input key="entry" value="Hello" style="text-align: right" /></div>'
        )

    try:
        first = reconciler.render(view(21))
        widget = first.children[0].handle.widget
        if backend == "qt":
            assert widget.font().pixelSize() == 21
            assert widget.font().family() == "Roboto"
        elif backend == "tk":
            assert widget._psx_css_native_font.cget("size") == -21
            assert str(widget.cget("justify")) == "right"
        else:
            assert widget.font_size == 21
            assert widget.halign == "right"
        updated = reconciler.render(view(26))
        assert updated.children[0].node.css_computed.properties["font-size"].value == 26
        assert updated.children[0].handle.widget is widget
        if backend == "qt":
            assert dict(widget._psx_css_font_revision)["font-size"] == 26
            assert widget.font().pixelSize() == 26
        elif backend == "tk":
            assert widget._psx_css_native_font.cget("size") == -26
        else:
            assert widget.font_size == 26
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag", ("h1", "h2", "h3", "h4", "h5", "h6", "p"))
def test_native_heading_paragraph_css_cascade_and_keyed_font_update(tag):
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    def view(size):
        return psx(
            f'<div><{tag} key="heading" style="font-size: {size}px; font-weight: 700;'
            f' color: #123456; text-align: right">Hello</{tag}></div>'
        )
    try:
        mounted = reconciler.render(view(22))
        leaf = mounted.children[0].children[0]
        widget = leaf.handle.widget
        if backend == "qt":
            assert widget.font().pixelSize() == 22
            assert widget.font().bold()
        elif backend == "tk":
            assert widget._psx_text_font.cget("size") == -22
            assert widget._psx_text_font.actual("weight") == "bold"
        else:
            assert widget.font_size == 22
            assert widget.bold
        mounted = reconciler.render(view(27))
        assert mounted.children[0].children[0].handle.widget is widget
        if backend == "qt":
            assert widget.font().pixelSize() == 27
        elif backend == "tk":
            assert widget._psx_text_font.cget("size") == -27
        else:
            assert widget.font_size == 27
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag,alias", (("Button", "button"), ("Input", "input")))
def test_native_css_foreground_applies_to_pascal_and_html_controls(tag, alias):
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color, html):
        name = alias if html else tag
        if name == "button":
            content = "Go"
        elif name == "Button":
            content = ""
        else:
            content = ""
        attrs = 'label="Go"' if name == "Button" else 'value="Go"' if name.lower() == "input" else ""
        return psx(
            f'<div><{name} key="color" {attrs} style="color: {color}">{content}</{name}></div>'
        )

    try:
        for html in (False, True):
            first = reconciler.render(view("#123456", html))
            widget = first.children[0].handle.widget
            if backend == "qt":
                assert "#123456" in widget.styleSheet()
            elif backend == "tk":
                if tag == "Input":
                    assert str(widget.cget("foreground")) == "#123456"
                else:
                    from tkinter import ttk
                    assert str(ttk.Style(widget).lookup(str(widget.cget("style")), "foreground")) == "#123456"
            else:
                assert tuple(widget.foreground_color if tag == "Input" else widget.color) == pytest.approx((18/255, 52/255, 86/255, 1))
            updated = reconciler.render(view("#654321", html))
            assert updated.children[0].handle.widget is widget
            if backend == "qt":
                assert "#654321" in widget.styleSheet()
            elif backend == "tk":
                if tag == "Input":
                    assert str(widget.cget("foreground")) == "#654321"
                else:
                    from tkinter import ttk
                    assert str(ttk.Style(widget).lookup(str(widget.cget("style")), "foreground")) == "#654321"
            else:
                assert tuple(widget.foreground_color if tag == "Input" else widget.color) == pytest.approx((101/255, 67/255, 33/255, 1))
    finally:
        reconciler.unmount()
        close()


def test_native_badge_css_foreground_is_applied_and_restored():
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        style = f' style="color: {color}"' if color else ""
        return psx(f'<div><Badge key="badge" label="New"{style} /></div>')

    try:
        mounted = reconciler.render(view("#123456"))
        widget = mounted.children[0].handle.widget
        if backend == "qt":
            assert widget._psx_css_foreground == "#123456"
        elif backend == "tk":
            assert widget._psx_css_foreground == "#123456"
            assert "#123456" in [str(widget.itemcget(i, "fill")) for i in widget.find_all() if widget.type(i) == "text"]
        else:
            assert tuple(widget.color) == pytest.approx((18/255, 52/255, 86/255, 1))
        mounted = reconciler.render(view(None))
        assert mounted.children[0].handle.widget is widget
        if backend in ("qt", "tk"):
            assert widget._psx_css_foreground is None
        else:
            assert tuple(widget.color) == pytest.approx(widget._psx_css_original_foreground)
    finally:
        reconciler.unmount()
        close()


def test_native_css_foreground_keeps_button_disabled_state():
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx(
            '<div><Button key="cta" label="Disabled" enabled={inactive} style="color: #123456" /></div>',
            scope={"inactive": False},
        ))
        widget = mounted.children[0].handle.widget
        if backend == "qt":
            assert not widget.isEnabled()
            assert "#123456" in widget.styleSheet()
        elif backend == "tk":
            assert "disabled" in str(widget.state())
            from tkinter import ttk
            assert ttk.Style(widget).lookup(str(widget.cget("style")), "foreground") == "#123456"
        else:
            assert widget.disabled
            assert tuple(widget.color) == pytest.approx((18/255, 52/255, 86/255, 1))
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag,alias", (("Button", "button"), ("Input", "input")))
def test_native_css_border_on_pascal_and_html_controls(tag, alias):
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color, html):
        name = alias if html else tag
        attrs = 'label="Go"' if name == "Button" else 'value="Go"' if name.lower() == "input" else ""
        content = "Go" if name == "button" else ""
        style = f' style="border-width: 2px; border-color: {color}"' if color else ""
        return psx(f'<div><{name} key="edge" {attrs}{style}>{content}</{name}></div>')

    try:
        for html in (False, True):
            first = reconciler.render(view("#123456", html))
            widget = first.children[0].handle.widget
            if backend == "qt":
                assert "2px solid #123456" in widget.styleSheet()
            elif backend == "tk":
                assert len(widget._psx_css_border_edges) == 4
                assert all(str(edge.cget("background")) == "#123456" for edge in widget._psx_css_border_edges)
            else:
                group, redraw, paint, line = widget._psx_css_control_stroke
                assert line.width == pytest.approx(1.0)
                assert line.force_custom_drawing_method
                assert tuple(paint.rgba) == pytest.approx((18/255, 52/255, 86/255, 1))
            changed = reconciler.render(view("#654321", html))
            assert changed.children[0].handle.widget is widget
            if backend == "qt":
                assert "2px solid #654321" in widget.styleSheet()
            elif backend == "tk":
                assert all(str(edge.cget("background")) == "#654321" for edge in widget._psx_css_border_edges)
            else:
                assert tuple(widget._psx_css_control_stroke[2].rgba) == pytest.approx((101/255, 67/255, 33/255, 1))
            reset = reconciler.render(view(None, html))
            assert reset.children[0].handle.widget is widget
            if backend == "qt":
                assert "2px solid" not in widget.styleSheet()
            elif backend == "tk":
                assert not hasattr(widget, "_psx_css_border_edges")
            else:
                assert not hasattr(widget, "_psx_css_control_stroke")
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag,alias", (("Button", "button"), ("Input", "input")))
def test_native_rounded_border_pascal_and_html_controls(tag, alias):
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(radius, html):
        name = alias if html else tag
        attrs = 'label="Go"' if name == "Button" else 'value="Go"' if name.lower() == "input" else ""
        text = "Go" if name == "button" else ""
        style = f' style="border-width: 2px; border-color: #8b5cf6; border-radius: {radius}px"'
        return psx(f'<div><{name} key="rounded" {attrs}{style}>{text}</{name}></div>')

    try:
        for html in (False, True):
            first = reconciler.render(view(8, html))
            widget = first.children[0].handle.widget
            if backend == "qt":
                assert "border-radius: 8px" in widget.styleSheet()
            elif backend == "tk":
                assert len(widget._psx_css_border_corners) == 4
                assert all(c.winfo_exists() for c in widget._psx_css_border_corners)
                assert all(len(c.find_all()) == 1 for c in widget._psx_css_border_corners)
            else:
                line = widget._psx_css_control_stroke[3]
                assert widget._psx_css_stroke_radius == pytest.approx(8)
            second = reconciler.render(view(12, html))
            assert second.children[0].handle.widget is widget
            if backend == "qt":
                assert "border-radius: 12px" in widget.styleSheet()
            elif backend == "tk":
                assert all(int(c.cget("width")) == 12 for c in widget._psx_css_border_corners)
            else:
                assert widget._psx_css_stroke_radius == pytest.approx(12)
            third = reconciler.render(view(0, html))
            assert third.children[0].handle.widget is widget
            if backend == "qt":
                assert "border-radius:" not in widget.styleSheet()
            elif backend == "tk":
                assert not hasattr(widget, "_psx_css_border_corners")
            else:
                assert not widget._psx_css_stroke_radius
    finally:
        reconciler.unmount()
        close()


def test_native_css_bottom_border_matches_qt_tk_and_kivy_without_other_sides():
    """A dashboard row divider is an owned one-sided stroke, never a frame."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color=None, thickness=2):
        style = (f"border-bottom: {thickness}px solid {color}" if color else "")
        return psx(
            f'<div><div key="row" style="{style}"><span>Recent</span></div></div>'
        )

    try:
        first = reconciler.render(view("#123456"))
        widget = first.children[0].handle.widget
        if backend == "qt":
            css = widget.styleSheet()
            assert "border-bottom: 2px solid #123456;" in css
            assert "border-top:" not in css
        elif backend == "tk":
            assert set(widget._psx_css_side_borders) == {"bottom"}
            assert str(widget._psx_css_side_borders["bottom"].cget("background")) == "#123456"
            assert not hasattr(widget, "_psx_css_border_edges")
        else:
            group, redraw, sides, lines = widget._psx_css_side_strokes
            assert group in widget.canvas.after.children
            assert len(lines) == 1 and lines[0][0] == "bottom"
            assert sides[0][1] == 2
            assert sides[0][2] == pytest.approx((18 / 255, 52 / 255, 86 / 255, 1))
            widget.pos = (11, 17)
            widget.size = (170, 40)
            assert list(lines[0][2].points) == pytest.approx([11, 18, 181, 18])

        updated = reconciler.render(view("#654321", 3))
        assert updated.children[0].handle.widget is widget
        if backend == "qt":
            assert "border-bottom: 3px solid #654321;" in widget.styleSheet()
        elif backend == "tk":
            assert set(widget._psx_css_side_borders) == {"bottom"}
            edge = widget._psx_css_side_borders["bottom"]
            assert str(edge.cget("background")) == "#654321"
            assert int(edge.place_info()["height"]) == 3
        else:
            group, redraw, sides, lines = widget._psx_css_side_strokes
            assert len(lines) == 1
            assert sides[0][1] == 3
            assert sides[0][2] == pytest.approx((101 / 255, 67 / 255, 33 / 255, 1))
            assert list(lines[0][2].points)[1] == pytest.approx(widget.y + 1.5)

        previous = getattr(widget, "_psx_css_side_strokes", None)
        reset = reconciler.render(view())
        assert reset.children[0].handle.widget is widget
        if backend == "qt":
            assert "border-bottom:" not in widget.styleSheet()
        elif backend == "tk":
            assert not getattr(widget, "_psx_css_side_borders", None)
        else:
            assert not hasattr(widget, "_psx_css_side_strokes")
            assert previous[0] not in widget.canvas.after.children
        reconciler.unmount()
        assert reconciler.root is None
    finally:
        reconciler.unmount()
        close()


def test_rounded_bottom_only_border_updates_without_painting_other_sides():
    """Qt, Tk and Kivy preserve a card's rounded CSS bottom divider."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    if backend == "tk":
        # A withdrawn Tk toplevel has no paint surface, even after an
        # idle-layout flush. These are native paint tests, not hidden
        # widget-creation tests: mount a real Xvfb window before readback.
        renderer.root.deiconify()
    reconciler = Reconciler(renderer)

    def view(color, radius=8):
        border = f"border-bottom: 2px solid {color}; " if color else ""
        return psx(
            '<div><div key="card" style="background-color: #fafafa; '
            f'{border}border-radius: {radius}px"><span>Recent</span>'
            '</div></div>'
        )

    try:
        mounted = reconciler.render(view("#123456"))
        widget = mounted.children[0].handle.widget
        if backend == "tk":
            renderer.root.update()
        if backend == "qt":
            assert "border-bottom: 2px solid #123456;" in widget.styleSheet()
            assert "border-radius: 8px;" in widget.styleSheet()
            assert "border-top:" not in widget.styleSheet()
        elif backend == "tk":
            surface = widget._psx_css_unified_surface
            assert surface.winfo_exists()
            assert widget._psx_css_unified_values[0] == 8
            assert set(widget._psx_css_unified_values[2]) == {"bottom"}
            assert widget._psx_css_unified_values[2]["bottom"] == (2.0, "#123456")
            assert not hasattr(widget, "_psx_css_side_borders")
            assert not hasattr(widget, "_psx_css_background_corners")
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
            assert len(surface.find_withtag("psx-css-surface-side")) == 1
        else:
            group, redraw, sides, lines = widget._psx_css_side_strokes
            assert len(lines) == 1 and lines[0][0] == "bottom"
            assert sides[0][2] == pytest.approx((18/255, 52/255, 86/255, 1))
            widget.pos = (12, 14)
            widget.size = (180, 50)
            points = list(lines[0][2].points)
            assert len(points) == 36
            assert min(points[1::2]) >= 14.9
            assert max(points[1::2]) < 14 + 8
            assert group in widget.canvas.after.children

        updated = reconciler.render(view("#123456", 12))
        assert updated.children[0].handle.widget is widget
        if backend == "qt":
            assert "border-radius: 12px;" in widget.styleSheet()
        elif backend == "tk":
            assert widget._psx_css_unified_surface is surface
            assert widget._psx_css_unified_values[0] == 12
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
        else:
            group2, _, styles2, lines2 = widget._psx_css_side_strokes
            assert group2 is group
            assert styles2 == sides
            assert widget._psx_css_side_radius == 12
            assert list(lines2[0][2].points) != points

        reset = reconciler.render(view(None, 0))
        assert reset.children[0].handle.widget is widget
        if backend == "qt":
            assert "border-bottom:" not in widget.styleSheet()
        elif backend == "tk":
            assert not getattr(widget, "_psx_css_side_borders", None)
            assert not hasattr(widget, "_psx_css_unified_surface")
            assert not surface.winfo_exists()
        else:
            assert not hasattr(widget, "_psx_css_side_strokes")
            assert group not in widget.canvas.after.children

    finally:
        reconciler.unmount()
        close()


def test_rounded_side_border_without_opaque_fill_preserves_backend_bounds():
    """Render an unfilled rounded side over the actual native parent surface."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    if backend == "tk":
        # A withdrawn Tk toplevel has no paint surface, even after an
        # idle-layout flush. These are native paint tests, not hidden
        # widget-creation tests: mount a real Xvfb window before readback.
        renderer.root.deiconify()
    reconciler = Reconciler(renderer)
    view = psx(
        '<div style="border-bottom: 2px solid #abcdef; border-radius: 8px">'
        '<span>Row</span></div>'
    )
    try:
        root = reconciler.render(view)
        if backend == "tk":
            renderer.root.update()
            surface = root.handle.widget._psx_css_unified_surface
            assert root.handle.widget._psx_css_unified_values[1] is None
            assert root.handle.widget._psx_css_unified_values[2]["bottom"] == (
                2.0, "#abcdef"
            )
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
            assert len(surface.find_withtag("psx-css-surface-side")) == 1
        elif backend == "qt":
            assert "border-bottom: 2px solid #abcdef;" in root.handle.widget.styleSheet()
            assert "border-radius: 8px;" in root.handle.widget.styleSheet()
        else:
            group, _, sides, lines = root.handle.widget._psx_css_side_strokes
            assert group in root.handle.widget.canvas.after.children
            assert sides[0][0] == "bottom"
            assert root.handle.widget._psx_css_side_radius == 8
            assert len(lines[0][2].points) == 36
    finally:
        reconciler.unmount()
        close()


def test_native_semantic_rounded_border_and_background_updates():
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    if backend == "tk":
        # A withdrawn Tk toplevel has no paint surface, even after an
        # idle-layout flush. These are native paint tests, not hidden
        # widget-creation tests: mount a real Xvfb window before readback.
        renderer.root.deiconify()
    reconciler = Reconciler(renderer)
    def view(radius):
        return psx(
            f'<div style="background-color: #ddeeff; border-width: 2px;'
            f' border-color: #123456; border-radius: {radius}px"><span>Content</span></div>'
        )
    try:
        first = reconciler.render(view(8))
        widget = first.handle.widget
        if backend == "tk":
            renderer.root.update()
        if backend == "qt":
            assert "border-radius: 8px" in widget.styleSheet()
        elif backend == "tk":
            surface = widget._psx_css_unified_surface
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
            assert not hasattr(widget, "_psx_css_border_corners")
            assert not hasattr(widget, "_psx_css_border_edges")
            assert set(widget._psx_css_unified_values[2]) == {
                "top", "right", "bottom", "left"
            }
        else:
            assert widget._psx_css_semantic_radius == pytest.approx(8)
            assert tuple(widget._psx_css_paint_rect.radius[0])[0] == pytest.approx(8)
        second = reconciler.render(view(12))
        assert second.handle.widget is widget
        if backend == "qt":
            assert "border-radius: 12px" in widget.styleSheet()
        elif backend == "tk":
            assert widget._psx_css_unified_surface is surface
            assert widget._psx_css_unified_values[0] == 12
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
            assert not hasattr(widget, "_psx_css_border_corners")
        else:
            assert widget._psx_css_semantic_radius == pytest.approx(12)
            assert tuple(widget._psx_css_paint_rect.radius[0])[0] == pytest.approx(12)
    finally:
        reconciler.unmount()
        close()


def test_native_semantic_named_red_rounded_background_without_border():
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    if backend == "tk":
        # A withdrawn Tk toplevel has no paint surface, even after an
        # idle-layout flush. These are native paint tests, not hidden
        # widget-creation tests: mount a real Xvfb window before readback.
        renderer.root.deiconify()
    reconciler = Reconciler(renderer)

    def view(color, radius):
        style = (f'background-color: {color}; border-radius: {radius}px'
                 if color else '')
        return psx(f'<div style="{style}"><p>Rounded background</p></div>')

    try:
        first = reconciler.render(view("red", 18))
        widget = first.handle.widget
        if backend == "tk":
            renderer.root.update()
        if backend == "qt":
            assert "background-color: #ff0000" in widget.styleSheet()
            assert "border-radius: 18px" in widget.styleSheet()
            assert widget.parentWidget() is not None
            assert widget.window() is not widget
            assert 0 < widget.height() < widget.window().height()
        elif backend == "tk":
            surface = widget._psx_css_unified_surface
            assert widget._psx_css_unified_values[:2] == (18, "#ff0000")
            assert len(surface.find_withtag("psx-css-surface-corner")) == 4
            assert len(surface._psx_css_corner_images) == 4
            assert not hasattr(widget, "_psx_css_background_corners")
        else:
            assert tuple(widget._psx_css_paint[2].rgba) == pytest.approx((1, 0, 0, 1))
            assert tuple(widget._psx_css_paint_rect.radius[0])[0] == pytest.approx(18)
        updated = reconciler.render(view("#0000ff", 8))
        assert updated.handle.widget is widget
        if backend == "qt":
            assert "border-radius: 8px" in widget.styleSheet()
        elif backend == "tk":
            assert widget._psx_css_unified_surface is surface
            assert widget._psx_css_unified_values[:2] == (8, "#0000ff")
        else:
            assert tuple(widget._psx_css_paint_rect.radius[0])[0] == pytest.approx(8)
        cleared = reconciler.render(view(None, 0))
        assert cleared.handle.widget is widget
        if backend == "qt":
            assert "border-radius" not in widget.styleSheet()
        elif backend == "tk":
            assert not hasattr(widget, "_psx_css_unified_surface")
            assert not surface.winfo_exists()
        else:
            assert not hasattr(widget, "_psx_css_paint")
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag,alias", (("Button", "button"), ("Input", "input")))
def test_native_control_font_measurement_revisions_are_incremental(tag, alias):
    """Typed font changes invalidate intrinsic measurement, color-only does not."""
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(size, color, html):
        name = alias if html else tag
        attrs = 'label="Reflow me"' if name == "Button" else 'value="Reflow me"'
        if name == "button":
            attrs = ""
        text = "Reflow me" if name == "button" else ""
        font = f"font-size: {size}px; font-family: Roboto; " if size else ""
        return psx(
            f'<div><{name} key="measure" {attrs} style="{font}color: {color}">'
            f'{text}</{name}></div>'
        )

    try:
        for html in (False, True):
            mounted = reconciler.render(view(18, "#123456", html))
            widget = mounted.children[0].handle.widget
            revision = widget._psx_css_font_revision
            assert dict(revision)["font-size"] == 18
            changed_color = reconciler.render(view(18, "#654321", html))
            assert changed_color.children[0].handle.widget is widget
            assert widget._psx_css_font_revision == revision

            larger = reconciler.render(view(26, "#654321", html))
            assert larger.children[0].handle.widget is widget
            assert dict(widget._psx_css_font_revision)["font-size"] == 26
            assert widget._psx_css_font_revision != revision

            cleared = reconciler.render(view(None, "#654321", html))
            assert cleared.children[0].handle.widget is widget
            assert dict(widget._psx_css_font_revision)["font-size"] is None
    finally:
        reconciler.unmount()
        close()


def test_native_text_line_height_and_content_measurement_revision():
    """Text nodes remeasure for leading/content changes and keep the native handle."""
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(text, leading, color):
        style = (f"font-size: 18px; line-height: {leading}px; "
                 f"color: {color}")
        return psx(f'<div><p key="paragraph" style="{style}">{text}</p></div>')

    try:
        first = reconciler.render(view("Short text", 36, "#123456"))
        widget = first.children[0].children[0].handle.widget
        first_revision = widget._psx_css_font_revision
        assert first_revision[0] == "Short text"
        assert dict(first_revision[1])["line-height"] == 36

        color_only = reconciler.render(view("Short text", 36, "#654321"))
        assert color_only.children[0].children[0].handle.widget is widget
        assert widget._psx_css_font_revision == first_revision

        leading_change = reconciler.render(view("Short text", 42, "#654321"))
        assert leading_change.children[0].children[0].handle.widget is widget
        assert dict(widget._psx_css_font_revision[1])["line-height"] == 42

        wrapped = reconciler.render(view("Longer text that can wrap onto multiple lines", 42, "#654321"))
        assert wrapped.children[0].children[0].handle.widget is widget
        assert widget._psx_css_font_revision[0] == "Longer text that can wrap onto multiple lines"

        removed = reconciler.render(psx('<div><p key="paragraph">Plain</p></div>'))
        assert removed.children[0].children[0].handle.widget is widget
        assert dict(widget._psx_css_font_revision[1])["line-height"] is None
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component", ("Link", "TextArea"))
def test_native_link_and_textarea_font_measurement_revisions(component):
    """Additional text-bearing controls update font measurements without a remount."""
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    prop = 'label="Example"' if component == "Link" else 'value="Several lines of text"'

    def view(size):
        style = f' style="font-size: {size}px; font-family: Roboto"' if size else ""
        return psx(f'<div><{component} key="typography" {prop}{style} /></div>')

    try:
        mounted = reconciler.render(view(18))
        widget = mounted.children[0].handle.widget
        assert dict(widget._psx_css_font_revision)["font-size"] == 18

        enlarged = reconciler.render(view(26))
        assert enlarged.children[0].handle.widget is widget
        assert dict(widget._psx_css_font_revision)["font-size"] == 26

        restored = reconciler.render(view(None))
        assert restored.children[0].handle.widget is widget
        assert dict(widget._psx_css_font_revision)["font-size"] is None
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("tag,content", (("Button", ""), ("button", "Save")))
def test_inherited_css_color_survives_native_disabled_state_transitions(tag, content):
    """Inherited paint and native enabled state evolve without replacing the handle."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color, enabled):
        attributes = 'label="Save"' if tag == "Button" else ""
        return psx(
            f'<div style="color: {color}"><{tag} key="action" {attributes} '
            f'enabled={{enabled}}>{content}</{tag}></div>',
            scope={"enabled": enabled},
        )

    try:
        mounted = reconciler.render(view("#123456", True))
        control = mounted.children[0].handle.widget
        assert mounted.children[0].node.css_computed.properties["color"].value == "#123456"

        for color, enabled in (("#654321", False), ("#123456", True)):
            updated = reconciler.render(view(color, enabled))
            assert updated.children[0].handle.widget is control
            if backend == "qt":
                assert control.isEnabled() is enabled
                assert color in control.styleSheet()
            elif backend == "tk":
                from tkinter import ttk
                assert ("disabled" in control.state()) is (not enabled)
                assert ttk.Style(control).lookup(
                    str(control.cget("style")), "foreground"
                ) == color
            else:
                assert control.disabled is (not enabled)
                assert tuple(control.color) == pytest.approx(
                    tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1,)
                )
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component,attribute", (
    ("Link", 'label="Documentation"'),
    ("TextArea", 'value="Editable text"'),
))
def test_native_text_controls_css_foreground_change_and_style_removal(component, attribute):
    """Mounted links and editors retain native identity and restore foreground."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        style = f' style="color: {color}"' if color is not None else ""
        return psx(
            f'<div><{component} key="control" {attribute}{style} /></div>'
        )

    def foreground(widget):
        if backend == "qt":
            return widget.styleSheet()
        if backend == "tk":
            return str(widget.cget("foreground"))
        value = widget.foreground_color if component == "TextArea" else widget.color
        return tuple(value)

    try:
        first = reconciler.render(view(None))
        widget = first.children[0].handle.widget
        original = foreground(widget)
        for color in ("#123456", "#654321"):
            current = reconciler.render(view(color))
            assert current.children[0].handle.widget is widget
            if backend == "qt":
                assert color in foreground(widget)
            elif backend == "tk":
                assert foreground(widget) == color
            else:
                expected = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1,)
                assert foreground(widget) == pytest.approx(expected)
        reset = reconciler.render(view(None))
        assert reset.children[0].handle.widget is widget
        if backend == "qt":
            assert "#654321" not in foreground(widget)
        elif backend == "tk":
            assert foreground(widget) == original
        else:
            assert foreground(widget) == pytest.approx(original)
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component,attributes", (
    ("Checkbox", 'checked={checked}'),
    ("Select", 'options={options} value="a"'),
    ("Badge", 'label="Status"'),
    ("Link", 'label="Open"'),
    ("TextArea", 'value="Editable"'),
))
def test_native_css_control_border_updates_and_owned_paint_cleanup(component, attributes):
    """Mounted component CSS strokes update in place and release owned overlays."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        paint = f' style="border-width: 2px; border-color: {color}; border-radius: 8px"' if color else ""
        scope = {"checked": True, "options": ({"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"})}
        return psx(f'<div><{component} key="native" {attributes}{paint} /></div>', scope=scope)

    try:
        mounted = reconciler.render(view("#123456"))
        widget = mounted.children[0].handle.widget
        if backend == "qt":
            if component == "Badge":
                # Badge has a custom painter and currently only projects foreground.
                assert not hasattr(widget, "_psx_css_base_stylesheet")
            else:
                assert "2px solid #123456" in widget.styleSheet()
        elif backend == "tk":
            assert len(widget._psx_css_border_edges) == 4
            assert all(edge.winfo_exists() for edge in widget._psx_css_border_edges)
        else:
            assert widget._psx_css_control_stroke[3].width == pytest.approx(1.0)
            assert widget._psx_css_control_stroke[3].force_custom_drawing_method

        changed = reconciler.render(view("#654321"))
        assert changed.children[0].handle.widget is widget
        if backend == "qt" and component != "Badge":
            assert "2px solid #654321" in widget.styleSheet()
        elif backend == "tk":
            assert all(str(edge.cget("background")) == "#654321"
                       for edge in widget._psx_css_border_edges)
        elif backend == "kivy":
            assert tuple(widget._psx_css_control_stroke[2].rgba) == pytest.approx(
                (101 / 255, 67 / 255, 33 / 255, 1)
            )

        restored = reconciler.render(view(None))
        assert restored.children[0].handle.widget is widget
        if backend == "qt" and component != "Badge":
            assert "2px solid" not in widget.styleSheet()
        elif backend == "tk":
            assert not hasattr(widget, "_psx_css_border_edges")
            assert not hasattr(widget, "_psx_css_border_corners")
        elif backend == "kivy":
            assert not hasattr(widget, "_psx_css_control_stroke")
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component,attrs", (
    ("Checkbox", 'checked={checked} enabled={enabled}'),
    ("Select", 'options={options} value="a" enabled={enabled}'),
    ("Link", 'label="Documentation" enabled={enabled}'),
    ("TextArea", 'value="Original" enabled={enabled} read_only={read_only}'),
))
def test_native_css_updates_preserve_control_state_and_owned_styling(component, attrs):
    """Changing CSS cannot replace a controlled native widget or its logical state."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    options = ({"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"})

    def view(color, enabled=True):
        style = f' style="color: {color}; border-width: 2px; border-color: #123456"' if color else ""
        return psx(
            f'<div><{component} key="stable" {attrs}{style} /></div>',
            scope={"enabled": enabled, "checked": True, "read_only": True, "options": options},
        )

    try:
        first = reconciler.render(view("#123456"))
        widget = first.children[0].handle.widget
        for color, enabled in (("#654321", False), ("#123456", True), (None, True)):
            updated = reconciler.render(view(color, enabled))
            assert updated.children[0].handle.widget is widget
            assert updated.children[0].node.props["enabled"] is enabled
            if backend == "qt":
                assert widget.isEnabled() is enabled
            elif backend == "tk":
                if component in ("Checkbox", "Select"):
                    assert ("disabled" in widget.state()) is (not enabled)
                elif component == "Link":
                    # tk.Label lacks a state option: the Link adapter gates
                    # activation through its stored props and native cursor.
                    assert widget._psx_link_props["enabled"] is enabled
                    assert str(widget.cget("cursor")) == ("hand2" if enabled else "arrow")
                else:
                    assert str(widget.cget("state")) in ("disabled", "normal")
            else:
                assert widget.disabled is (not enabled)
            if component == "Checkbox":
                assert updated.children[0].node.props["checked"] is True
            elif component == "Select":
                assert updated.children[0].node.props["value"] == "a"
            elif component == "TextArea":
                assert updated.children[0].node.props["read_only"] is True
        reconciler.unmount()
        if backend == "tk":
            assert not widget.winfo_exists()
        elif backend == "kivy":
            assert not hasattr(widget, "_psx_css_control_stroke")
    finally:
        reconciler.unmount()
        close()


def test_native_radio_group_css_keeps_selection_callbacks_and_child_identity():
    """CSS-only updates do not disturb radio grouping, selection, or event slots."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend, sfle=False)
    reconciler = Reconciler(renderer)
    events = []

    def view(color, selected, generation):
        css = f' style="color: {color}; border-color: {color}; border-width: 2px"' if color else ""
        return psx(
            f'<RadioGroup key="group" value="{selected}" on_change={{callback}}>'
            f'<Radio key="a" value="a" label="Alpha"{css}/>'
            f'<Radio key="b" value="b" label="Beta"{css}/>'
            '</RadioGroup>',
            scope={"callback": lambda value: events.append((generation, value))},
        )

    def selected(widget):
        if backend == "qt":
            return widget.isChecked()
        if backend == "tk":
            return widget._psx_var.get()
        return widget._psx_checkbox.active

    try:
        first = reconciler.render(view("#123456", "a", 1))
        group = first
        group_widget = group.handle.widget
        radio_a, radio_b = (item.handle.widget for item in group.children)
        if backend == "qt":
            assert radio_a.isChecked()
            assert "#123456" in radio_a.styleSheet()
        elif backend == "tk":
            assert group_widget._psx_var.get() == "a"
            assert len(radio_a._psx_css_border_edges) == 4
        else:
            assert radio_a._psx_checkbox.active
            assert tuple(radio_a._psx_label.color) == pytest.approx(
                (18 / 255, 52 / 255, 86 / 255, 1)
            )

        updated = reconciler.render(view("#654321", "a", 2))
        assert updated.handle.widget is group_widget
        assert updated.children[0].handle.widget is radio_a
        assert updated.children[1].handle.widget is radio_b

        if backend == "qt":
            assert radio_a.isChecked()
            radio_b.click()
        elif backend == "tk":
            assert group_widget._psx_var.get() == "a"
            group_widget._psx_var.set("b")
        else:
            assert radio_a._psx_checkbox.active
            radio_b._psx_checkbox.active = True
        assert events == [(2, "b")]

        restored = reconciler.render(view(None, "b", 3))
        assert restored.handle.widget is group_widget
        assert restored.children[1].handle.widget is radio_b
        if backend == "qt":
            assert radio_b.isChecked()
            assert "#654321" not in radio_b.styleSheet()
        elif backend == "tk":
            assert group_widget._psx_var.get() == "b"
            assert not hasattr(radio_b, "_psx_css_border_edges")
        else:
            assert radio_b._psx_checkbox.active
            assert not hasattr(radio_b, "_psx_css_control_stroke")
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component", ("Checkbox", "Link"))
def test_native_css_style_updates_keep_live_control_callbacks(component):
    """Native interactions use the latest callback after style-only keyed updates."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    seen = []

    def view(color, generation):
        style = (f' style="border-width: 2px; border-color: {color}"'
                 if color else "")
        if component == "Checkbox":
            element = (
                f'<Checkbox key="interactive" checked={{checked}} '
                f'on_change={{callback}}{style}/>'
            )
            callback = lambda value: seen.append((generation, bool(value)))
        else:
            element = f'<Link key="interactive" label="Read" on_click={{callback}}{style}/>'
            callback = lambda: seen.append((generation, "click"))
        return psx(
            "<div>" + element + "</div>",
            scope={"callback": callback, "checked": False},
        )

    def activate(widget):
        if component == "Checkbox":
            if backend == "qt":
                widget.setChecked(not widget.isChecked())
            elif backend == "tk":
                widget.invoke()
            else:
                widget.active = not widget.active
        else:
            if backend == "qt":
                widget.click()
            elif backend == "tk":
                from psx.renderers.tkinter.link import TkLinkAdapter
                TkLinkAdapter._activate(widget)
            else:
                widget.dispatch("on_release")

    try:
        first = reconciler.render(view("#123456", 1))
        widget = first.children[0].handle.widget
        slot = first.children[0].event_slots[
            "on_change" if component == "Checkbox" else "on_click"
        ][0]
        activate(widget)
        assert [event[0] for event in seen] == [1]

        second = reconciler.render(view("#654321", 2))
        assert second.children[0].handle.widget is widget
        assert second.children[0].event_slots[
            "on_change" if component == "Checkbox" else "on_click"
        ][0] is slot
        activate(widget)
        assert [event[0] for event in seen] == [1, 2]

        restored = reconciler.render(view(None, 3))
        assert restored.children[0].handle.widget is widget
        activate(widget)
        assert [event[0] for event in seen] == [1, 2, 3]
        reconciler.unmount()
        old_events = tuple(seen)
        if component == "Checkbox":
            slot.invoke(True)
        else:
            slot.invoke()
        assert tuple(seen) == old_events
        if backend == "tk":
            assert not widget.winfo_exists()
    finally:
        reconciler.unmount()
        close()


def test_native_select_css_retains_selection_and_latest_user_callback():
    """Controlled selection and the native on_change binding survive CSS updates."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    events = []
    options = ({"label": "Alpha", "value": "a"},
               {"label": "Beta", "value": "b"})

    def view(color, selected, generation):
        style = f' style="color: {color}; border-width: 2px; border-color: {color}"' if color else ""
        return psx(
            f'<div><Select key="choice" options={{options}} value="{selected}" '
            f'on_change={{callback}}{style}/></div>',
            scope={"options": options,
                   "callback": lambda value: events.append((generation, value))},
        )

    def select_value(widget, value):
        if backend == "qt":
            index = widget.findData(value)
            assert index >= 0
            widget.setCurrentIndex(index)
        elif backend == "tk":
            index = next(i for i, (_label, item) in enumerate(widget._psx_items)
                         if item == value)
            widget.current(index)
            widget.event_generate("<<ComboboxSelected>>", when="now")
        else:
            widget.text = {"a": "Alpha", "b": "Beta"}[value]

    try:
        initial = reconciler.render(view("#123456", "a", 1))
        widget = initial.children[0].handle.widget
        slot = initial.children[0].event_slots["on_change"][0]
        updated = reconciler.render(view("#654321", "a", 2))
        assert updated.children[0].handle.widget is widget
        assert updated.children[0].event_slots["on_change"][0] is slot
        select_value(widget, "b")
        assert events and events[-1] == (2, "b")

        cleared = reconciler.render(view(None, "b", 3))
        assert cleared.children[0].handle.widget is widget
        select_value(widget, "a")
        assert events[-1] == (3, "a")
        reconciler.unmount()
        before = tuple(events)
        slot.invoke("b")
        assert tuple(events) == before
    finally:
        reconciler.unmount()
        close()


def test_native_textarea_css_preserves_selection_readonly_and_edit_callbacks():
    """CSS-only changes preserve native editor selection, identity and live events."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    changes = []

    def view(color, readonly, generation):
        style = f' style="color: {color}; font-size: 20px"' if color else ""
        return psx(
            f'<div><TextArea key="editor" value="Editable text" '
            f'read_only={{readonly}} on_change={{callback}}{style}/></div>',
            scope={"readonly": readonly,
                   "callback": lambda value: changes.append((generation, value))},
        )

    try:
        initial = reconciler.render(view("#123456", False, 1))
        widget = initial.children[0].handle.widget
        slot = initial.children[0].event_slots["on_change"][0]
        if backend == "qt":
            widget.selectAll()
            assert widget.textCursor().selectedText() == "Editable text"
        elif backend == "tk":
            widget.tag_add("sel", "1.0", "1.6")
            assert len(widget.tag_ranges("sel")) == 2
        else:
            widget.select_text(0, 6)
            assert widget.selection_text == "Editab"

        updated = reconciler.render(view("#654321", False, 2))
        assert updated.children[0].handle.widget is widget
        assert updated.children[0].event_slots["on_change"][0] is slot
        if backend == "qt":
            assert widget.textCursor().selectedText() == "Editable text"
        elif backend == "tk":
            assert len(widget.tag_ranges("sel")) == 2
        else:
            assert widget.selection_text == "Editab"

        locked = reconciler.render(view("#654321", True, 3))
        assert locked.children[0].handle.widget is widget
        if backend == "qt":
            assert widget.isReadOnly()
        elif backend == "tk":
            assert str(widget.cget("state")) == "disabled"
        else:
            assert widget.readonly is True

        restored = reconciler.render(view(None, False, 4))
        assert restored.children[0].handle.widget is widget
        if backend == "qt":
            assert not widget.isReadOnly()
            widget.setPlainText("Changed")
        elif backend == "tk":
            assert str(widget.cget("state")) == "normal"
            widget.delete("1.0", "end")
            widget.insert("1.0", "Changed")
            widget.edit_modified(True)
            widget.event_generate("<<Modified>>", when="now")
        else:
            assert widget.readonly is False
            widget.text = "Changed"
        assert changes and changes[-1] == (4, "Changed")

        reconciler.unmount()
        previous = tuple(changes)
        slot.invoke("after unmount")
        assert tuple(changes) == previous
        if backend == "tk":
            assert not widget.winfo_exists()
    finally:
        reconciler.unmount()
        close()


def test_native_css_visual_paint_is_instance_scoped_and_cleans_up():
    """CSS ownership cannot modify an unstyled sibling or the global Tk theme."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        style = (
            f' style="color: {color}; border-width: 2px; border-color: {color}"'
            if color else ""
        )
        return psx(
            '<div><Button key="painted" label="Painted"' + style +
            ' /><Button key="untouched" label="Untouched"/></div>'
        )

    try:
        first = reconciler.render(view(None))
        painted, untouched = (node.handle.widget for node in first.children)
        if backend == "qt":
            original_style = painted.styleSheet()
            sibling_style = untouched.styleSheet()
        elif backend == "tk":
            from tkinter import ttk
            theme = ttk.Style(painted)
            theme_color = theme.lookup("TButton", "foreground")
            sibling_style = str(untouched.cget("style"))
            original_style = str(painted.cget("style"))
        else:
            baseline_instructions = len(painted.canvas.after.children)
            sibling_instructions = len(untouched.canvas.after.children)

        for color in ("#123456", "#654321", "#123456"):
            mounted = reconciler.render(view(color))
            assert mounted.children[0].handle.widget is painted
            assert mounted.children[1].handle.widget is untouched
            if backend == "qt":
                assert color in painted.styleSheet()
                assert "2px solid" in painted.styleSheet()
                assert untouched.styleSheet() == sibling_style
            elif backend == "tk":
                assert painted._psx_css_border_edges
                assert all(str(edge.cget("background")) == color
                           for edge in painted._psx_css_border_edges)
                assert str(untouched.cget("style")) == sibling_style
                assert theme.lookup("TButton", "foreground") == theme_color
                assert str(painted.cget("style")) != sibling_style
            else:
                assert hasattr(painted, "_psx_css_control_stroke")
                assert len(painted.canvas.after.children) == baseline_instructions + 1
                assert len(untouched.canvas.after.children) == sibling_instructions

        restored = reconciler.render(view(None))
        assert restored.children[0].handle.widget is painted
        if backend == "qt":
            assert painted.styleSheet() == original_style
            assert untouched.styleSheet() == sibling_style
        elif backend == "tk":
            assert not hasattr(painted, "_psx_css_border_edges")
            assert str(painted.cget("style")) == original_style
            assert str(untouched.cget("style")) == sibling_style
            assert theme.lookup("TButton", "foreground") == theme_color
        else:
            assert not hasattr(painted, "_psx_css_control_stroke")
            assert len(painted.canvas.after.children) == baseline_instructions
            assert len(untouched.canvas.after.children) == sibling_instructions

        reconciler.unmount()
        if backend == "tk":
            assert not painted.winfo_exists()
            assert not untouched.winfo_exists()
    finally:
        reconciler.unmount()
        close()


def test_qt_css_merges_manually_installed_native_stylesheets():
    """A Qt Link keeps its native QSS and later user overrides across CSS commits."""
    from psx.markup.compile import psx

    if os.environ["PSX_GRID_BACKEND"] != "qt":
        pytest.skip("QSS is specific to the Qt renderer")

    renderer, close = make_renderer("qt")
    reconciler = Reconciler(renderer)

    def view(color):
        style = f' style="color: {color}; border-width: 2px; border-color: {color}"' if color else ""
        return psx(f'<div><Link key="link" label="Documentation"{style}/></div>')

    try:
        first = reconciler.render(view("#123456"))
        widget = first.children[0].handle.widget
        original_qss = widget._psx_css_base_stylesheet
        assert "background: transparent" in original_qss
        assert widget.styleSheet().rstrip().endswith("}")
        assert "color: #123456" in widget.styleSheet()

        manual_qss = "QPushButton { padding: 7px; }"
        widget.setStyleSheet(manual_qss)
        changed = reconciler.render(view("#654321"))
        assert changed.children[0].handle.widget is widget
        assert manual_qss in widget.styleSheet()
        assert "color: #654321" in widget.styleSheet()
        assert widget.styleSheet().rstrip().endswith("}")

        removed = reconciler.render(view(None))
        assert removed.children[0].handle.widget is widget
        assert widget.styleSheet() == manual_qss
    finally:
        reconciler.unmount()
        close()


def test_native_editor_css_keeps_focus_capability_and_active_focus_when_available():
    """Paint-only updates leave native focus support and any acquired focus intact."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        style = f' style="color: {color}; border-width: 2px; border-color: #123456"' if color else ""
        return psx(f'<div><TextArea key="focus" value="Focusable"{style}/></div>')

    try:
        first = reconciler.render(view(None))
        widget = first.children[0].handle.widget
        if backend == "qt":
            original = widget.focusPolicy()
            widget.setFocus()
            had_focus = widget.hasFocus()
        elif backend == "tk":
            original = str(widget.cget("takefocus"))
            widget.focus_set()
            had_focus = widget.focus_get() is widget
        else:
            widget.focus = True
            had_focus = bool(widget.focus)
            assert had_focus

        changed = reconciler.render(view("#654321"))
        assert changed.children[0].handle.widget is widget
        if backend == "qt":
            assert widget.focusPolicy() == original
            if had_focus:
                assert widget.hasFocus()
        elif backend == "tk":
            assert str(widget.cget("takefocus")) == original
            if had_focus:
                assert widget.focus_get() is widget
        else:
            assert widget.focus

        cleared = reconciler.render(view(None))
        assert cleared.children[0].handle.widget is widget
        if backend == "qt":
            assert widget.focusPolicy() == original
            if had_focus:
                assert widget.hasFocus()
        elif backend == "tk":
            assert str(widget.cget("takefocus")) == original
            if had_focus:
                assert widget.focus_get() is widget
        else:
            assert widget.focus
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("component,attrs", (
    ("Button", 'label="Go"'),
    ("Checkbox", 'checked={checked}'),
    ("Select", 'options={options} value="a"'),
    ("TextArea", 'value="Editable"'),
    ("Link", 'label="Visit"'),
    ("Badge", 'label="New"'),
))
def test_native_css_teardown_releases_active_control_paint(component, attrs):
    """Unmount cleans owned native paint even when CSS was never reset first."""
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    options = ({"label": "Alpha", "value": "a"},)
    scope = {"options": options, "checked": True}

    try:
        root = reconciler.render(psx(
            f'<div><{component} key="paint" {attrs} '
            'style="color: #123456; border-width: 2px; border-color: #123456"/>'
            '</div>',
            scope=scope,
        ))
        widget = root.children[0].handle.widget
        if backend == "kivy":
            group = widget._psx_css_control_stroke[0]
            assert group in widget.canvas.after.children
        elif backend == "tk":
            edges = widget._psx_css_border_edges
            assert len(edges) == 4
            assert all(edge.winfo_exists() for edge in edges)
        elif component == "Badge":
            assert widget._psx_css_foreground == "#123456"
        else:
            assert "2px solid #123456" in widget.styleSheet()
        reconciler.unmount()
        assert reconciler.root is None
        if backend == "kivy":
            assert not hasattr(widget, "_psx_css_control_stroke")
            assert group not in widget.canvas.after.children
        elif backend == "tk":
            assert not widget.winfo_exists()
            assert all(not edge.winfo_exists() for edge in edges)
    finally:
        reconciler.unmount()
        close()


def test_native_css_paint_burst_does_not_commit_cinnamon_geometry(request):
    """Record native renderer latency and actual commit counts, not inferred speedups."""
    from time import perf_counter_ns, process_time_ns
    import tracemalloc
    from psx.markup.compile import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    calls = 0
    original_commit = renderer.commit_layout

    def counted(root):
        nonlocal calls
        calls += 1
        return original_commit(root)

    renderer.commit_layout = counted

    def view(color, width=180):
        # Cinnamon's root border box must equal the native viewport.
        # Change the child width, never the fixed-size 800x200 host.
        return psx(
            f'<div style="width: 800px; height: 200px; color: {color}">'
            f'<button key="save" label="Save" style="width: {width}px" />'
            '</div>'
        )

    try:
        mounted = reconciler.render(view("#123456"))
        widget = mounted.children[0].handle.widget
        initial = rectangle(widget, backend)
        assert calls == 1
        own_tracemalloc = not tracemalloc.is_tracing()
        if own_tracemalloc:
            tracemalloc.start()
        snapshot_bytes = tracemalloc.get_traced_memory()[0]
        started_cpu = process_time_ns()
        started = perf_counter_ns()
        for index in range(100):
            color = "#123456" if index % 2 else "#654321"
            next_view = view(color)
            from psx.core.reconcile import _paint_only_css_update
            accepted = _paint_only_css_update(reconciler.root, next_view)
            state = getattr(renderer, "_sfle_measurement_invalidations", None)
            pending_before = tuple(sorted(state.pending)) if state is not None else ()
            updated = reconciler.render(next_view)
            assert updated.children[0].handle.widget is widget
            assert rectangle(widget, backend) == initial
            assert calls == 1, (
                f"paint index={index}, accepted={accepted}, "
                f"pending_before={pending_before}, "
                f"pending_after={tuple(sorted(state.pending)) if state else ()}"
            )
        elapsed = perf_counter_ns() - started
        cpu_elapsed = process_time_ns() - started_cpu
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        if own_tracemalloc:
            tracemalloc.stop()
        # All hundred updates changed visual CSS, not dimensions. Native
        # widget identity and geometry remain stable across the burst.
        assert calls == 1
        request.node.user_properties.append(
            ("paint_100_elapsed_ns", elapsed)
        )
        request.node.user_properties.append(
            ("paint_100_layout_commits", calls - 1)
        )
        request.node.user_properties.append(
            ("paint_100_cpu_ns", cpu_elapsed)
        )
        request.node.user_properties.append(
            ("paint_100_memory_growth_bytes", current_bytes - snapshot_bytes)
        )
        request.node.user_properties.append(
            ("paint_100_tracemalloc_peak_bytes", peak_bytes)
        )
        request.node.user_properties.append(
            ("backend", backend)
        )

        started = perf_counter_ns()
        resized = reconciler.render(view("#123456", 210))
        assert resized.children[0].handle.widget is widget
        assert calls == 2
        request.node.user_properties.append(
            ("geometry_update_elapsed_ns", perf_counter_ns() - started)
        )
    finally:
        reconciler.unmount()
        close()


def test_kivy_multiline_css_line_height_keeps_native_measurement_revision_and_identity():
    """Kivy's bounded native line-height contract is a line-height ratio."""
    if os.environ["PSX_GRID_BACKEND"] != "kivy":
        pytest.skip("Kivy-only multiline native leading readback")
    from psx.markup.compile import psx
    renderer, close = make_renderer("kivy")
    reconciler = Reconciler(renderer)

    def view(leading):
        style = (f' style="font-size: 18px; line-height: {leading}px"'
                 if leading is not None else '')
        return psx(
            f'<div><p key="leading"{style}>'
            'Several words here should wrap over multiple lines'
            '</p></div>'
        )

    try:
        mounted = reconciler.render(view(36))
        widget = mounted.children[0].children[0].handle.widget
        assert widget.line_height == pytest.approx(2.0)
        assert dict(widget._psx_css_font_revision[1])["line-height"] == 36

        larger = reconciler.render(view(45))
        assert larger.children[0].children[0].handle.widget is widget
        assert widget.line_height == pytest.approx(2.5)
        assert dict(widget._psx_css_font_revision[1])["line-height"] == 45

        cleared = reconciler.render(view(None))
        assert cleared.children[0].children[0].handle.widget is widget
        assert widget.line_height == pytest.approx(widget.property("line_height").defaultvalue)
        assert dict(widget._psx_css_font_revision[1])["line-height"] is None
    finally:
        reconciler.unmount()
        close()


@pytest.mark.parametrize("shade", ("#123456", "#abcdef", "#ff0000"))
def test_native_css_certified_background_update_and_reset(shade):
    """P1.4.8 checks a real host painter across all three native adapters."""
    from psx.markup.compile import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    def view(color):
        style = f' style="background-color: {color}"' if color else ""
        return psx(f'<div{style}><button key="stay" label="Save"/></div>')

    try:
        mounted = reconciler.render(view(shade))
        host = mounted.handle.widget
        button = mounted.children[0].handle.widget
        if backend == "qt":
            assert shade in host.styleSheet()
        elif backend == "tk":
            from tkinter import ttk
            assert str(ttk.Style(host).lookup(host.cget("style"), "background")).lower() == shade
        else:
            rgba = tuple(int(shade[i:i+2], 16) / 255 for i in (1, 3, 5))
            assert tuple(host._psx_css_paint[2].rgba)[:3] == pytest.approx(rgba)
        changed = reconciler.render(view("#654321"))
        assert changed.handle.widget is host
        assert changed.children[0].handle.widget is button
        removed = reconciler.render(view(None))
        assert removed.handle.widget is host
        assert removed.children[0].handle.widget is button
        if backend == "qt":
            assert "background-color: #654321" not in host.styleSheet()
    finally:
        reconciler.unmount()
        close()


def test_native_event_replacement_and_teardown_disconnects_real_toolkit_callbacks():
    """Exercise actual Qt signals, Tk commands and Kivy event dispatch."""
    from psx import Button

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend, sfle=False)
    reconciler = Reconciler(renderer)
    calls = []
    try:
        for cycle in range(8):
            original = reconciler.render(
                Button("Action", on_click=lambda n=cycle: calls.append(("old", n)))
            )
            widget = original.handle.widget
            if backend == "qt":
                widget.click()
            elif backend == "tk":
                widget.invoke()
            else:
                widget.dispatch("on_release")
            updated = reconciler.render(
                Button("Action", on_click=lambda n=cycle: calls.append(("new", n)))
            )
            assert updated.handle.widget is widget
            slot = updated.event_slots["on_click"][0]
            if backend == "qt":
                widget.click()
            elif backend == "tk":
                widget.invoke()
            else:
                widget.dispatch("on_release")
            assert calls[-2:] == [("old", cycle), ("new", cycle)]
            if cycle == 4:
                original_unbind = renderer.unbind_event

                def disconnect_then_fail(subscription):
                    original_unbind(subscription)
                    raise RuntimeError("native disconnect failure")

                renderer.unbind_event = disconnect_then_fail
                try:
                    with pytest.raises(RuntimeError, match="native disconnect failure"):
                        reconciler.unmount()
                finally:
                    renderer.unbind_event = original_unbind
            else:
                reconciler.unmount()
            assert reconciler.root is None
            assert updated.disposed
            assert updated.event_slots == {}
            assert slot.invoke() is None
            if backend == "qt":
                renderer.application.processEvents()
                # Queued Qt deleteLater may require a deferred-delete flush.
                core = importlib.import_module(
                    {"pyside6": "PySide6", "pyside2": "PySide2",
                     "pyqt5": "PyQt5", "pyqt6": "PyQt6"}[
                        os.environ["PSX_QT_BINDING"]] + ".QtCore")
                core.QCoreApplication.sendPostedEvents(
                    None, core.QEvent.Type.DeferredDelete)
                if os.environ["PSX_QT_BINDING"].startswith("pyside"):
                    wrapper = importlib.import_module(
                        "shiboken6" if os.environ["PSX_QT_BINDING"] == "pyside6"
                        else "shiboken2")
                    assert not wrapper.isValid(widget)
                else:
                    sip = importlib.import_module(
                        "PyQt6.sip" if os.environ["PSX_QT_BINDING"] == "pyqt6"
                        else "sip")
                    assert sip.isdeleted(widget)
            elif backend == "tk":
                assert not widget.winfo_exists()
            else:
                assert widget.parent is None
        assert len(calls) == 16
    finally:
        reconciler.unmount()
        close()


def test_disposed_native_component_ignores_queued_state_ui_callbacks():
    """Qt/Tk/Kivy must not re-render a destroyed widget from a late UI flush."""
    from psx import component, use_state

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend, sfle=False)
    tree = Reconciler(renderer)
    setters = []
    renders = []

    @component
    def Counter():
        value, setter = use_state(0)
        setters.append(setter)
        renders.append(value)
        return Text(str(value))

    try:
        for _ in range(8):
            tree.render(Counter())
            setter = setters.pop()
            setter(1)
            tree.unmount()
            if backend == "qt":
                renderer.application.processEvents()
            elif backend == "tk":
                renderer.flush()
            else:
                from kivy.clock import Clock
                Clock.tick()
            assert tree.root is None
        assert renders == [0] * 8
    finally:
        tree.unmount()
        close()


def _flush_qt_disposal(renderer):
    """Qt processEvents alone does not guarantee deleteLater delivery."""
    binding = os.environ["PSX_QT_BINDING"]
    module = {"pyside6": "PySide6", "pyside2": "PySide2",
              "pyqt5": "PyQt5", "pyqt6": "PyQt6"}[binding]
    core = importlib.import_module(module + ".QtCore")
    renderer.application.processEvents()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.Type.DeferredDelete)


def test_native_image_churn_releases_owned_decoded_buffers(tmp_path):
    """Image adapters release their own decoded resources on every unmount."""
    import base64
    from psx import Image

    png = tmp_path / "pixel.png"
    png.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    ))
    backend = os.environ["PSX_GRID_BACKEND"]
    soak_report = os.environ.get("PSX_SOAK_REPORT")
    cycles = int(os.environ.get("PSX_SOAK_CYCLES", "12"))
    if cycles <= 0:
        raise ValueError("Native image soak requires positive cycles.")
    if soak_report:
        import gc
        import json
        import platform
        import sys
        import time
        import tracemalloc
        from benchmarks.resource_baseline import process_memory
        tracemalloc.start()
        starting_memory = process_memory()
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()
        checkpoints = []
        cycle_times_ns = []
    renderer, close = make_renderer(backend, sfle=False)
    tree = Reconciler(renderer)
    try:
        for cycle in range(cycles):
            if soak_report:
                cycle_start_ns = time.perf_counter_ns()
            mounted = tree.render(Image(str(png), width=10, height=10))
            handle = mounted.handle
            widget = handle.widget
            tree.unmount()
            assert tree.root is None
            assert handle.props == {}
            assert widget._psx_props is None
            if backend == "qt":
                assert widget._psx_pixmap_cache is None
                _flush_qt_disposal(renderer)
            elif backend == "tk":
                assert widget._psx_image_cache is None
                assert widget._psx_photo is None
                assert not widget.winfo_exists()
            else:
                assert widget._psx_sfle_invalidate is None
                assert widget.parent is None
            if soak_report:
                cycle_times_ns.append(time.perf_counter_ns() - cycle_start_ns)
            if soak_report and ((cycle + 1) % max(1, cycles // 4) == 0 or cycle + 1 == cycles):
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                checkpoints.append({"cycle": cycle + 1, "traced_current_bytes": current,
                                    "traced_peak_bytes": peak, "gc_objects": len(gc.get_objects()),
                                    "process_memory": process_memory()})
    finally:
        tree.unmount()
        close()
        if soak_report:
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            report = {"schema": 1, "backend": backend,
                      "qt_binding": os.environ.get("PSX_QT_BINDING") if backend == "qt" else None,
                      "python": sys.version.split()[0], "platform": platform.platform(),
                      "cycles": cycles, "checkpoints": checkpoints,
                      "mean_cycle_ms": round(sum(cycle_times_ns) / len(cycle_times_ns) / 1e6, 4),
                      "p95_cycle_ms": round(sorted(cycle_times_ns)[(len(cycle_times_ns) * 95 + 99) // 100 - 1] / 1e6, 4),
                      "process_memory_before": starting_memory,
                      "process_memory_after": process_memory(),
                      "after_teardown_traced_bytes": current, "traced_peak_bytes": peak,
                      "wall_total_ms": round((time.perf_counter_ns() - wall_start) / 1e6, 3),
                      "cpu_total_ms": round((time.process_time_ns() - cpu_start) / 1e6, 3),
                      "scope": "real native image mount/unmount; not a GPU allocator leak verdict"}
            from pathlib import Path
            Path(soak_report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            tracemalloc.stop()


def test_native_keyed_tree_reconciliation_soak():
    """Measure sustained native subtree mount, reordering and teardown."""
    import gc
    from collections import Counter
    import weakref
    import json
    import platform
    import sys
    import time
    import tracemalloc
    from pathlib import Path
    from psx import Button, Flex
    from benchmarks.resource_baseline import process_memory

    backend = os.environ["PSX_GRID_BACKEND"]
    report_path = os.environ.get("PSX_TREE_SOAK_REPORT")
    cycles = int(os.environ.get("PSX_TREE_SOAK_CYCLES", "12"))
    assert cycles > 0
    renderer, close = make_renderer(backend, sfle=True)
    tree = Reconciler(renderer)
    checkpoints = []
    object_type_baseline = None
    object_type_final = None
    target_samples = []
    cycle_times_ns = []
    tracemalloc.start()
    baseline_memory = process_memory()
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()

    try:
        for cycle in range(cycles):
            cycle_start_ns = time.perf_counter_ns()
            first = Flex(
                Button("A", key="a", on_click=lambda: None),
                Text(str(cycle), key="b"),
                direction="column",
            )
            second = Flex(
                Text(str(cycle + 1), key="b"),
                Button("A", key="a", on_click=lambda: None),
                direction="column",
            )
            tree.render(first)
            tree.render(second)
            tree.unmount()
            assert tree.root is None
            if backend == "qt":
                _flush_qt_disposal(renderer)
            elif backend == "tk":
                renderer.flush()
            else:
                from kivy.clock import Clock
                Clock.tick()
            cycle_times_ns.append(time.perf_counter_ns() - cycle_start_ns)
            if (cycle + 1) % max(1, cycles // 4) == 0 or cycle + 1 == cycles:
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                counts = Counter(f"{type(obj).__module__}.{type(obj).__qualname__}" for obj in gc.get_objects())
                if object_type_baseline is None:
                    object_type_baseline = counts
                object_type_final = counts
                all_objects = gc.get_objects()
                weakrefs = [obj for obj in all_objects if type(obj) is weakref.ReferenceType]
                targets = Counter("dead" if item() is None else f"{type(item()).__module__}.{type(item()).__qualname__}" for item in weakrefs)
                target_samples.append({"cycle": cycle + 1, "weakref_targets": targets.most_common(16)})
                del weakrefs, all_objects
                checkpoints.append({
                    "cycle": cycle + 1,
                    "traced_current_bytes": current,
                    "traced_peak_bytes": peak,
                    "gc_objects": len(gc.get_objects()),
                    "process_memory": process_memory(),
                })
        if (backend == "qt" and cycles >= 512
                and os.environ["PSX_QT_BINDING"].startswith("pyside")):
            # Calibrated on real PySide2/6 512-cycle benchmarks: after caching
            # QObject subclass types, wrapper/tuple drift is at most 22/1.
            # Allow CI allocator variance but reject per-widget linear growth.
            accumulated = object_type_final - object_type_baseline
            assert accumulated.get("weakref.ReferenceType", 0) <= 64
            assert accumulated.get("builtins.tuple", 0) <= 64
    finally:
        tree.unmount()
        close()
        if report_path:
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            report = {
                "schema": 1, "backend": backend,
                "qt_binding": os.environ.get("PSX_QT_BINDING") if backend == "qt" else None,
                "python": sys.version.split()[0], "platform": platform.platform(),
                "cycles": cycles, "checkpoints": checkpoints,
                "gc_object_type_growth": (object_type_final - object_type_baseline).most_common(25),
                "gc_weakref_target_snapshots": target_samples,
                "mean_cycle_ms": round(sum(cycle_times_ns) / len(cycle_times_ns) / 1e6, 4),
                "p95_cycle_ms": round(sorted(cycle_times_ns)[(len(cycle_times_ns) * 95 + 99) // 100 - 1] / 1e6, 4),
                "process_memory_before": baseline_memory,
                "process_memory_after": process_memory(),
                "after_teardown_traced_bytes": current, "traced_peak_bytes": peak,
                "wall_total_ms": round((time.perf_counter_ns() - start_wall) / 1e6, 3),
                "cpu_total_ms": round((time.process_time_ns() - start_cpu) / 1e6, 3),
                "scope": "real native keyed tree and widget lifecycle; diagnostic, not leak verdict",
            }
            Path(report_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        tracemalloc.stop()


def test_qt_binding_only_signal_wrapper_reference_soak():
    """Reference workload isolating Qt binding allocations from PSX retention."""
    if os.environ["PSX_GRID_BACKEND"] != "qt":
        pytest.skip("Qt binding-only reference workload")
    import gc
    import json
    import tracemalloc
    from collections import Counter
    from pathlib import Path
    from benchmarks.resource_baseline import process_memory

    binding = os.environ["PSX_QT_BINDING"]
    package = {"pyside6": "PySide6", "pyside2": "PySide2",
               "pyqt5": "PyQt5", "pyqt6": "PyQt6"}[binding]
    widgets = importlib.import_module(package + ".QtWidgets")
    core = importlib.import_module(package + ".QtCore")
    app = widgets.QApplication.instance() or widgets.QApplication(["psx-wrapper-reference"])
    cycles = int(os.environ.get("PSX_TREE_SOAK_CYCLES", "12"))
    report_path = os.environ.get("PSX_BINDING_REFERENCE_REPORT")
    assert cycles > 0
    tracemalloc.start()
    checkpoints = []
    baseline_counts = None
    final_counts = None
    before_process = process_memory()

    try:
        for cycle in range(cycles):
            # Each PSX event binding constructs a fresh application callback;
            # reusing one callback would hide binding-level identity caches.
            on_click = lambda current=cycle: current
            parent = widgets.QWidget()
            button = widgets.QPushButton(parent)
            button.clicked.connect(on_click)
            button.click()
            button.clicked.disconnect(on_click)
            parent.deleteLater()
            del parent, button
            app.processEvents()
            core.QCoreApplication.sendPostedEvents(None, core.QEvent.Type.DeferredDelete)
            if (cycle + 1) % max(1, cycles // 4) == 0 or cycle + 1 == cycles:
                gc.collect()
                counts = Counter(f"{type(obj).__module__}.{type(obj).__qualname__}" for obj in gc.get_objects())
                if baseline_counts is None:
                    baseline_counts = counts
                final_counts = counts
                traced, peak = tracemalloc.get_traced_memory()
                checkpoints.append({"cycle": cycle + 1,
                                    "gc_objects": len(gc.get_objects()),
                                    "traced_current_bytes": traced,
                                    "traced_peak_bytes": peak,
                                    "process_memory": process_memory()})
    finally:
        if report_path:
            report = {
                "schema": 1, "binding": binding, "cycles": cycles,
                "checkpoints": checkpoints,
                "gc_object_type_growth": (final_counts - baseline_counts).most_common(25),
                "process_memory_before": before_process,
                "process_memory_after": process_memory(),
                "scope": "Qt-only QWidget plus signal churn; no PSX reconciler/layout",
            }
            Path(report_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        tracemalloc.stop()


def test_qt_viewport_filter_class_is_reused_and_owned_callbacks_are_discarded():
    """Repeated native commits must not create a QObject subclass per mount."""
    if os.environ["PSX_GRID_BACKEND"] != "qt":
        pytest.skip("Qt-specific QObject observer lifetime")
    from psx import Flex

    renderer, close = make_renderer("qt", sfle=True)
    tree = Reconciler(renderer)
    filter_class = None
    try:
        for cycle in range(16):
            tree.render(Flex(Text(str(cycle)), width="100%", height=200))
            active_filter = renderer._sfle_resize_filter
            assert active_filter is not None
            if filter_class is None:
                filter_class = type(active_filter)
            assert type(active_filter) is filter_class
            tree.unmount()
            assert renderer._sfle_resize_filter is None
            assert active_filter._resize_handler is None
            assert active_filter._invalidation_handler is None
            _flush_qt_disposal(renderer)
    finally:
        tree.unmount()
        close()


def test_qt_text_and_button_host_types_remain_constant_across_mounts():
    """A new native widget must not create a new Qt QObject-derived Python type."""
    if os.environ["PSX_GRID_BACKEND"] != "qt":
        pytest.skip("Qt wrapper class ownership")
    from psx import Button, Flex

    renderer, close = make_renderer("qt", sfle=True)
    tree = Reconciler(renderer)
    reference_types = None
    try:
        for cycle in range(16):
            mounted = tree.render(Flex(
                Text(str(cycle), key="text"),
                Button("Action", key="button"),
                direction="column", width="100%", height=200))
            current_types = tuple(type(child.handle.widget) for child in mounted.children)
            if reference_types is None:
                reference_types = current_types
            assert current_types == reference_types
            tree.unmount()
            _flush_qt_disposal(renderer)
    finally:
        tree.unmount()
        close()


def test_css_div_flex_row_gap_renders_distinct_native_positions():
    from psx.css.markup import compute_markup_styles
    from psx import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        source = psx("<div><p>Alpha</p><p>Beta</p></div>")
        styled = compute_markup_styles(
            source, "div { display: flex; gap: 10px; flex-direction: row; }")
        root = reconciler.render(styled)
        first, second = (child.handle.widget for child in root.children)
        left = rectangle(first, backend)
        right = rectangle(second, backend)
        assert right[0] >= left[0] + left[2] + 9
        assert renderer.sfle_result is not None
        assert renderer.sfle_result.geometry_commit_error <= 1
    finally:
        reconciler.unmount()
        close()


def test_sidebar_nested_block_preserves_inline_button_flow_and_auto_footer():
    """Browser-like navigation in a column Flex on all native adapters."""
    from psx.css.markup import compute_markup_styles
    from psx import psx

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    document = compute_markup_styles(psx("""
        <div class="sidebar">
            <div class="navigation">
                <button>Inicio</button>
                <button>Configuración</button>
            </div>
            <div class="sidebar-footer"><p>Mi perfil</p></div>
        </div>
    """), """
        .sidebar {
            display: flex;
            flex-direction: column;
            height: 100vh;
            background: red;
        }
        .sidebar-footer { margin-top: auto; }
    """)
    try:
        mounted = reconciler.render(document)
        for height in (200, 500, 320):
            constraints = LayoutConstraints(
                AvailableSize(800, True), AvailableSize(height, True))
            renderer.set_sfle_constraints(constraints)
            renderer.commit_layout(mounted)
            boxes = [box.border for _, box in renderer.sfle_result.boxes]
            # Root, navigation, two native buttons, footer, paragraph, text.
            assert len(boxes) >= 6
            root_box, nav, first, second, footer = boxes[:5]
            assert first.y == pytest.approx(second.y, abs=1)
            assert second.x >= first.x + first.width - 1
            assert second.x + second.width <= nav.x + nav.width + 1
            assert footer.y >= nav.y + nav.height - 1
            assert footer.y + footer.height == pytest.approx(
                root_box.y + root_box.height, abs=1,
            )
            assert renderer.sfle_result.geometry_commit_error <= 1
    finally:
        reconciler.unmount()
        close()


def test_css_display_switch_reflows_same_semantic_native_div():
    from psx.css.markup import compute_markup_styles
    from psx import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        source = psx("<div><p>Alpha</p><p>Beta</p></div>")
        column = compute_markup_styles(source, "div { display: block; }")
        row = compute_markup_styles(source,
            "div { display: flex; gap: 10px; flex-direction: row; }")
        first = reconciler.render(column)
        host = first.handle.widget
        assert first.children[0].handle.widget is not first.children[1].handle.widget
        second = reconciler.render(row)
        assert second.handle.widget is host
        a, b = (child.handle.widget for child in second.children)
        left, right = rectangle(a, backend), rectangle(b, backend)
        assert right[0] >= left[0] + left[2] + 9
        restored = reconciler.render(column)
        assert restored.handle.widget is host
        assert renderer.sfle_result is not None
    finally:
        reconciler.unmount()
        close()


def test_css_flex_div_uses_content_height_without_painting_full_viewport():
    from psx import psx
    from psx.css.markup import compute_markup_styles
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    try:
        markup = psx('<div style="background: #ff0000"><p>Small</p></div>')
        styled = compute_markup_styles(markup, "div { display: flex; }")
        root = reconciler.render(styled)
        native = root.handle.widget
        result = renderer.sfle_result
        root_box = dict(result.boxes)[result.boxes[0][0]].border
        assert 0 < root_box.height < 200
        if backend == "kivy":
            assert native.height == pytest.approx(200)
            assert native._psx_css_paint_rect.size[1] == pytest.approx(root_box.height)
        elif backend == "tk":
            assert float(native.place_info()["height"]) == pytest.approx(root_box.height, abs=1)
        else:
            assert native.height() == pytest.approx(root_box.height, abs=1)
    finally:
        reconciler.unmount()
        close()


def test_fragment_root_mounts_multiple_html_siblings_on_native_backends():
    from psx import component, psx, use_state
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)

    @component
    def Example():
        value, _ = use_state(21)
        return psx(
            f"<><h1>Hello World!</h1><p>Welcome to Velto</p>"
            f"<p>Count: {value}</p><button>Increment</button></>"
        )

    try:
        boundary = reconciler.render(Example())
        assert boundary.node.kind.value == "component"
        viewport_host = boundary.children[0]
        assert viewport_host.node.type == "div"
        assert [c.node.type for c in viewport_host.children] == [
            "h1", "p", "p", "Button",
        ]
        boxes = dict(renderer.sfle_result.boxes)
        assert len(boxes) >= 8
        head, welcome, counter, button = viewport_host.children
        assert rectangle(head.handle.widget, backend)[2] > 0
        assert rectangle(button.handle.widget, backend)[2] < 800
        assert renderer.sfle_result.geometry_commit_error <= 1
    finally:
        reconciler.unmount()
        close()


def test_grid_composition_reused_for_same_width_within_transaction(monkeypatch):
    """Repeated intrinsic requests must not repeat native Grid measurement."""
    from threading import get_ident
    from types import SimpleNamespace
    from psx.sfle.grid_native_commit import GridCommitBackend
    from psx.sfle.grid_native_commit import GridCommitBackend
    from psx.sfle import mixed_grid_native
    from psx.sfle.mixed_grid_native import MountedMixedGrid

    calls = []
    composition = SimpleNamespace(content_height=75)
    def measure(grid, **kwargs):
        calls.append(kwargs["content_width"])
        return composition

    monkeypatch.setattr(mixed_grid_native, "prepare_composed_grid", measure)
    bridge = object.__new__(MountedMixedGrid)
    bridge.renderer = SimpleNamespace(
        _sfle_owner_thread=get_ident(), _sfle_generation=4,
        _sfle_engine=object(), _sfle_constraints=viewport(800),
    )
    bridge.generation = 4
    bridge.grids = {"cards": object()}
    bridge.handles = {}
    bridge.backend = GridCommitBackend.QT
    bridge.breakpoints = {}
    bridge._composition_cache = {}
    assert bridge.intrinsic("cards", 500).preferred_height == 75
    assert bridge.intrinsic("cards", 500).preferred_height == 75
    assert bridge.compose("cards", 500) is composition
    assert calls == [500]
    bridge.compose("cards", 540)
    assert calls == [500, 540]
    bridge.renderer._sfle_generation = 5
    with pytest.raises(Exception, match="stale"):
        bridge.compose("cards", 500)


def test_tk_mixed_grid_syncs_native_idle_once_per_composition(monkeypatch):
    """A composed Grid cannot drain the entire Tcl idle queue per leaf."""
    from threading import get_ident
    from types import SimpleNamespace
    from psx.sfle import mixed_grid_native, tk_measurement
    from psx.sfle.mixed_grid_native import MountedMixedGrid
    from psx.sfle.grid_native_commit import GridCommitBackend
    from psx.sfle.model import IntrinsicSizes

    drains, measured, synced = [], [], []
    source = object()
    leaf = SimpleNamespace(source=source)
    widget = object()

    class NativeSource:
        def __init__(self, widgets, *, idle_synced=False):
            assert widgets == {"text": widget}
            synced.append(idle_synced)

        def measure_width(self, identifier, width):
            measured.append((identifier, width))
            return IntrinsicSizes(10, 10, 10, 10, 10, 10)

    def compose(_grid, **kwargs):
        for index in range(6):
            kwargs["measure_leaf"]("text", leaf, 50 + index)
        return SimpleNamespace(content_height=20)

    monkeypatch.setattr(tk_measurement, "TkMeasurementSource", NativeSource)
    monkeypatch.setattr(mixed_grid_native, "prepare_composed_grid", compose)
    bridge = object.__new__(MountedMixedGrid)
    bridge.renderer = SimpleNamespace(
        _sfle_owner_thread=get_ident(), _sfle_generation=1,
        _sfle_engine=object(), _sfle_constraints=viewport(800),
        root=SimpleNamespace(update_idletasks=lambda: drains.append(1)),
    )
    bridge.generation = 1
    bridge.grids = {"cards": object()}
    bridge.handles = {id(source): SimpleNamespace(widget=widget)}
    bridge.backend = GridCommitBackend.TK
    bridge.breakpoints = {}
    bridge._composition_cache = {}
    assert bridge.compose("cards", 500).content_height == 20
    assert bridge.compose("cards", 500).content_height == 20
    assert bridge.compose("cards", 540).content_height == 20
    # Distinct widths cause new compositions, but only one baseline
    # settlement per bridge/generation; width-dependent leaves still probe.
    assert len(drains) == 1
    assert len(measured) == 12
    assert synced == [True] * 12


def test_grid_composition_failure_is_not_cached(monkeypatch):
    from threading import get_ident
    from types import SimpleNamespace
    from psx.sfle.grid_native_commit import GridCommitBackend
    from psx.sfle import mixed_grid_native
    from psx.sfle.mixed_grid_native import MountedMixedGrid

    count = [0]
    def measure(grid, **kwargs):
        count[0] += 1
        if count[0] == 1:
            raise RuntimeError("measurement failed")
        return SimpleNamespace(content_height=15)
    monkeypatch.setattr(mixed_grid_native, "prepare_composed_grid", measure)
    bridge = object.__new__(MountedMixedGrid)
    bridge.renderer = SimpleNamespace(
        _sfle_owner_thread=get_ident(), _sfle_generation=1,
        _sfle_engine=object(), _sfle_constraints=viewport(800),
    )
    bridge.generation = 1
    bridge.grids = {"cards": object()}
    bridge.handles = {}
    bridge.backend = GridCommitBackend.QT
    bridge.breakpoints = {}
    bridge._composition_cache = {}
    with pytest.raises(RuntimeError, match="measurement failed"):
        bridge.compose("cards", 500)
    assert bridge.compose("cards", 500).content_height == 15
    assert count == [2]



@pytest.mark.parametrize('wrapped_root', [False, True])
def test_scroll_wrapped_grid_item_uses_native_viewport_across_backends(wrapped_root, request):
    """The scroll viewport owns clipping; Grid owns the item's track width."""
    from psx import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    reconciler = Reconciler(renderer)
    markup = (
        ('<div><Grid gap="0px">' if wrapped_root else '<Grid gap="0px">')
        + '<GridItem span="3"><div><p>Sidebar</p></div></GridItem>'
        + '<Scroll direction="vertical" height="100vh"><GridItem>'
        + '<div><p>Contenido</p><p>Más contenido</p></div>'
        + '</GridItem></Scroll>'
        + ('</Grid></div>' if wrapped_root else '</Grid>')
    )
    try:
        root = reconciler.render(psx(markup))
        grid = root.children[0] if wrapped_root else root
        assert [node.node.type for node in grid.children] == ["GridItem", "GridItem"]
        scrolling = grid.children[1].children[0]
        assert scrolling.node.type == "Scroll"
        assert scrolling.node.props["layout_height"] == "100vh"
        assert rectangle(scrolling.handle.widget, backend)[3] == pytest.approx(200, abs=1)
        native = scrolling.handle.widget
        assert getattr(native, "_psx_sfle_scroll", False)
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(900, True), AvailableSize(280, True)))
        renderer.commit_layout(root)
        assert scrolling.handle.widget is native
        assert rectangle(native, backend)[3] == pytest.approx(280, abs=1)
        assert renderer.grid_result is not None
        binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
            "tkinter" if backend == "tk" else "kivy")
        assert_feature(
            request,
            Feature("Grid", binding, "interaction", "scroll_wrapped_item",
                    ("nested" if wrapped_root else "root") + "_viewport_resize",
                    applicability="partial_native"),
            True,
        )
    finally:
        reconciler.unmount()
        close()


def test_kivy_trackpad_grid_item_scroll_does_not_shift_content_on_vertical_resize():
    """Real Grid > Scroll > GridItem keeps its content origin while panning."""
    if os.environ.get("PSX_GRID_BACKEND") != "kivy":
        pytest.skip("Kivy-specific native scroll coordinate reproduction")
    from psx import psx
    from kivy.uix.scrollview import ScrollView

    renderer, close = make_renderer("kivy")
    tree = Reconciler(renderer)
    paragraphs = "".join(f"<p>Activity entry {n}</p>" for n in range(50))
    markup = (
        '<div><Grid gap="0px">'
        '<GridItem span="3"><div><p>Sidebar</p></div></GridItem>'
        '<Scroll direction="vertical" height="100vh"><GridItem>'
        # The CSS root has a short fixed border box while the final paragraph
        # extends far below it. This reproduces the full-extent Kivy bug.
        '<div class="content" style="height: 160px; background: #202630;">'
        '<p style="margin: 0px;">Start of dashboard</p>'
        '<div class="container"><Grid gap="16px">'
        '<GridItem span="6"><div><p>Users</p></div></GridItem>'
        '<GridItem span="6"><div><p>Sales</p></div></GridItem>'
        '</Grid></div>'
        + paragraphs
        + '<p style="margin: 0px;">End of dashboard</p>'
        + '</div></GridItem></Scroll></Grid></div>'
    )
    try:
        root = tree.render(psx(markup))
        grid = root.children[0]
        scroll = grid.children[1].children[0]
        native = scroll.handle.widget
        assert isinstance(native, ScrollView)
        assert native.always_overscroll is False
        # Scroll > GridItem > div; the HTML root fills the renderer-owned
        # content viewport, not the short visible Scroll rectangle.
        html_root = scroll.children[0].children[0]
        content_root = html_root.handle.widget
        first = html_root.children[0].handle.widget
        last = html_root.children[-1].handle.widget
        assert native._psx_content.height > native.height
        native.scroll_y = 0.4
        for height in (280, 360, 190, 420, 210):
            renderer.set_sfle_constraints(LayoutConstraints(
                AvailableSize(900, True), AvailableSize(height, True)))
            renderer.commit_layout(root)
            assert scroll.handle.widget is native
            assert native._psx_content.height > native.height
            assert content_root.y - content_root.parent.y == pytest.approx(0, abs=1)
            assert content_root.height == pytest.approx(
                native._psx_content.height, abs=1,
            )
            # ScrollView translates its content by -(extent - viewport) at
            # scroll_y=1 and by 0 at scroll_y=0. The first and last native
            # widgets must stay inside those two reachable extremes.
            extent = native._psx_content.height
            assert first.top - content_root.y == pytest.approx(extent, abs=2)
            assert last.y >= content_root.y - 2
            assert 0 <= native.scroll_y <= 1
            assert renderer.grid_result is not None
    finally:
        tree.unmount()
        close()


def test_grid_flow_leaf_remeasures_after_content_change():
    """Per-composition measurements must never outlive a content update."""
    from psx import psx
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        first = tree.render(psx(
            '<div><Grid gap="0px"><GridItem span="12">'
            '<div><p key="copy">Short</p></div>'
            '</GridItem></Grid></div>'
        ))
        grid = first.children[0]
        widget = grid.children[0].children[0].children[0].handle.widget
        first_width = rectangle(widget, backend)[2]
        second = tree.render(psx(
            '<div><Grid gap="0px"><GridItem span="12">'
            '<div><p key="copy">A substantially longer paragraph of native text</p></div>'
            '</GridItem></Grid></div>'
        ))
        assert second.children[0].children[0].children[0].children[0].handle.widget is widget
        assert rectangle(widget, backend)[2] >= first_width
        assert renderer.grid_result is not None
        assert renderer.grid_result[1].max_readback_error <= 1
    finally:
        tree.unmount()
        close()


def test_tk_grid_resize_does_not_publish_parent_before_child_geometry():
    """The staged Grid root keeps its prior rectangle until native commit."""
    if os.environ.get("PSX_GRID_BACKEND") != "tk":
        pytest.skip("Tk-specific staged root")
    renderer, close = make_renderer("tk")
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(view())
        frame = root.handle.widget
        prior = rectangle(frame, "tk")
        renderer.set_sfle_constraints(viewport(960))
        assert rectangle(frame, "tk") == prior
        renderer.commit_layout(root)
        assert rectangle(frame, "tk")[2] == 960
        assert renderer.grid_result[1].max_readback_error <= 1
    finally:
        reconciler.unmount()
        close()
