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


def test_grid_requires_explicit_scroll_flex_content(request):
    """Scroll must expose explicit Flex content; a direct Grid cannot bypass it."""
    from psx import Scroll
    from psx.core.errors import RendererCapabilityError

    backend = os.environ["PSX_GRID_BACKEND"]
    binding = os.environ["PSX_QT_BINDING"] if backend == "qt" else (
        "tkinter" if backend == "tk" else "kivy")
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        with pytest.raises(RendererCapabilityError, match="explicit Flex content root"):
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
        with pytest.raises(GridPackingError, match="Composite GridItem"):
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
            assert widget._psx_text_font.cget("family") == "Roboto"
            assert widget._psx_text_font.actual("weight") == "bold"
            assert str(widget.cget("foreground")) == "#123456"
            assert widget.cget("justify") == "center"
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
