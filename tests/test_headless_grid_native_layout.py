"""Mounted Headless Grid contract: actual reconciliation, geometry and resize."""
from __future__ import annotations

import pytest

from psx import Grid, GridItem, Text
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature


def viewport(width):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(100, True))


def make_renderer(width=800):
    def measure(node, allocated_width):
        assert node.type == "Text"
        height = 30 if allocated_width < 390 else 10
        return IntrinsicSizes(0, allocated_width, 0, height, allocated_width, height)
    return HeadlessRenderer(
        sfle_constraints=viewport(width),
        engine=PythonLayoutEngine(),
        measure_intrinsic=measure,
    )


def tree(order=("a", "b")):
    return Grid(*(
        GridItem(Text(label, key="leaf"), span={"base": 12, "md": 6}, key=label)
        for label in order
    ), gap=4)


def test_mounted_grid_native_geometry_and_intrinsic_readback(request):
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(tree())
    a, b = root.children
    assert root.handle.geometry.width == 800
    assert a.handle.geometry.width == 398
    assert b.handle.geometry.x == 402
    assert a.children[0].handle.geometry.width == 398
    assert a.children[0].handle.geometry.height == 10
    assert renderer.grid_result[1].max_readback_error == 0
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "geometry_readback", applicability="partial_native"), True)
    assert_feature(request, Feature("GridItem", "headless", "interaction", "native_child", "geometry_readback", applicability="partial_native"), True)
    reconciler.unmount()
    assert renderer.grid_result is None
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "teardown", applicability="partial_native"), True)


def test_mounted_grid_reflow_and_keyed_reorder_preserve_handles(request):
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(tree())
    handles = {child.node.key: child.handle for child in root.children}
    renderer.set_sfle_constraints(viewport(767))
    renderer.commit_layout(root)
    assert root.children[0].handle.geometry.width == 767
    assert root.children[1].handle.geometry.y == 14
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "resize_reflow", applicability="partial_native"), True)
    reordered = reconciler.render(tree(("b", "a")))
    assert reordered.children[0].handle is handles["b"]
    assert reordered.children[1].handle is handles["a"]
    assert reordered.children[0].handle.geometry.y == 0
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "keyed_reorder", applicability="partial_native"), True)
    reconciler.unmount()


def test_grid_requires_real_width_aware_intrinsic_callback():
    renderer = HeadlessRenderer(sfle_constraints=viewport(800), engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    with pytest.raises(Exception, match="width-aware"):
        reconciler.render(tree())


def test_grid_fails_closed_without_sfle_viewport():
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    with pytest.raises(Exception, match="SFLE Grid layout backend"):
        reconciler.render(tree())


@pytest.mark.parametrize("start,expected", ((767, 767), (800, 398)))
def test_grid_breakpoint_cycle_preserves_identity_and_stable_geometry(request, start, expected):
    """Repeated breakpoint crossings remain deterministic without remounting."""
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(tree())
        handles = tuple((item.handle, item.children[0].handle) for item in root.children)
        for width in (start, 800 if start == 767 else 767, start):
            renderer.set_sfle_constraints(viewport(width))
            renderer.commit_layout(root)
            assert renderer.grid_result[1].max_readback_error == 0
        assert root.children[0].handle.geometry.width == expected
        assert root.children[1].handle.geometry.width == expected
        assert tuple((item.handle, item.children[0].handle) for item in root.children) == handles
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "responsive_cycle",
            f"width_{start}_{expected}", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_nested_grid_independent_content_breakpoint_and_lifecycle(request):
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    nested = Grid(
        GridItem(
            Grid(
                GridItem(Text("nested a"), key="a", span={"base": 12, "md": 6}),
                GridItem(Text("nested b"), key="b", span={"base": 12, "md": 6}),
                gap=4,
            ),
            key="nested", span={"base": 12, "md": 6},
        ),
        GridItem(Text("outer"), key="outer", span={"base": 12, "md": 6}),
        gap=4,
    )
    try:
        root = reconciler.render(nested)
        subgrid = root.children[0].children[0]
        first = subgrid.children[0].handle
        second = subgrid.children[1].handle
        assert first.geometry.width == 398
        renderer.set_sfle_constraints(viewport(1600))
        renderer.commit_layout(root)
        assert first.geometry.width == 397
        assert second.geometry.width == 397
        assert subgrid.children[0].handle is first
        renderer.set_sfle_constraints(viewport(800))
        renderer.commit_layout(root)
        assert first.geometry.width == 398
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "nested_content_width",
            "independent_breakpoint_reflow", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_nested_grid_observes_application_breakpoint_configuration(request):
    from psx.app import App

    def nested_tree():
        return Grid(
            GridItem(Grid(
                GridItem(Text("a"), key="a", span={"base": 12, "md": 6}),
                GridItem(Text("b"), key="b", span={"base": 12, "md": 6}),
                gap=4,
            ), key="nested", span={"base": 12, "md": 6}),
            GridItem(Text("right"), key="right", span={"base": 12, "md": 6}),
            gap=4,
        )

    renderer = make_renderer()
    application = App(nested_tree(), renderer=renderer, settings={
        "grid": {"breakpoints": {"base": 0, "sm": 100, "md": 350,
                                  "lg": 700, "xl": 900}},
    })
    try:
        root = application.reconciler.render(application.root)
        nested_a = root.children[0].children[0].children[0].handle
        assert nested_a.geometry.width == 197
        renderer.set_sfle_constraints(viewport(600))
        renderer.commit_layout(root)
        assert nested_a.geometry.width == 298
        assert root.children[0].children[0].children[0].handle is nested_a
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "configured_container_breakpoints",
            "isolated_nested_resolution", applicability="partial_native"), True)
    finally:
        application.unmount()


def test_flex_grid_mixed_headless_width_allocation_readback_and_identity(request):
    from psx import Flex
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(Flex(
            Grid(
                GridItem(Text("left"), key="left", span={"base": 12, "md": 6}),
                GridItem(Text("right"), key="right", span={"base": 12, "md": 6}),
                gap=4,
            ),
            direction="column", width="100%", height=100,
        ))
        grid = root.children[0]
        first = grid.children[0].handle
        leaf = grid.children[0].children[0].handle
        assert grid.handle.geometry.width == 800
        assert first.geometry.width == 398
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(root)
        assert grid.handle.geometry.width == 767
        assert first.geometry.width == 767
        assert grid.children[0].handle is first
        assert grid.children[0].children[0].handle is leaf
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "mixed_flex",
            "allocated_width_reflow", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_headless_grid_inside_scroll_flex_preserves_layout_identity(request):
    """Headless certifies geometry, not native wheel/keyboard interactions."""
    from psx import Flex, Scroll
    from psx.sfle.model import IntrinsicSizes
    def metric(node, allocated_width=None):
        if node.type == "Text":
            width = allocated_width if allocated_width is not None else 20
            return IntrinsicSizes(0, width, 0, 10, width, 10)
        return IntrinsicSizes(0, 0, 0, 0, 0, 0)
    renderer = HeadlessRenderer(
        sfle_constraints=viewport(800),
        engine=PythonLayoutEngine(), measure_intrinsic=metric,
    )
    def scene(width):
        return Flex(
            Scroll(
                Flex(tree(), direction="column", width=width, height="240px",
                     key="content", align_items="stretch"),
                key="viewport", direction="both",
                layout_width="120px", layout_height="80px",
                flex_basis="120px", flex_shrink=0,
            ),
            direction="row", width="800px", height="100px",
            align_items="flex-start",
        )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(scene("800px"))
        grid = mounted.children[0].children[0].children[0]
        original = grid.children[0].handle
        assert grid.handle.geometry.width == 800
        assert original.geometry.width == 398
        changed = reconciler.render(scene("600px"))
        grid = changed.children[0].children[0].children[0]
        assert grid.children[0].handle is original
        assert grid.handle.geometry.width == 600
        assert original.geometry.width == 600
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "mixed_scroll",
            "geometry_and_identity", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_headless_mixed_grid_rollback_and_recovery(request, monkeypatch):
    """Mixed root and Grid descendants share one rollback boundary."""
    from psx import Flex
    from psx.sfle import grid_native_commit
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(Flex(tree(), direction="column", width="100%", height=100))
        grid = mounted.children[0]
        leaf = grid.children[0].children[0].handle
        first = grid.children[0].handle
        renderer.set_sfle_constraints(viewport(767))
        previous = (grid.handle.geometry, first.geometry, leaf.geometry)
        with monkeypatch.context() as patch:
            def fail(*args, **kwargs):
                raise RuntimeError("simulated mixed Headless Grid failure")
            patch.setattr(grid_native_commit, "commit_grid_native_geometry", fail)
            with pytest.raises(RuntimeError, match="simulated mixed Headless"):
                renderer.commit_layout(mounted)
        assert (grid.handle.geometry, first.geometry, leaf.geometry) == previous
        renderer.commit_layout(mounted)
        assert first.geometry.width == 767
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "mixed_transaction",
            "rollback_and_recovery", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_grid_item_supports_cinnamon_flex_content_and_native_children(request):
    from psx import Flex
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    def scene():
        return Grid(
            GridItem(
                Flex(
                    Text("a", key="a", layout_width="80px", layout_height="20px",
                         flex_basis="80px", flex_shrink=0),
                    Text("b", key="b", layout_width="80px", layout_height="20px",
                         flex_basis="80px", flex_shrink=0),
                    direction="row", width="100%", height="50px",
                    align_items="flex-start", gap=4,
                ),
                key="flex", span=12,
            ), gap=4,
        )
    try:
        mounted = reconciler.render(scene())
        flex = mounted.children[0].children[0]
        a, b = flex.children
        assert flex.handle.geometry.width == 800
        assert a.handle.geometry.width == 80
        assert b.handle.geometry.x > a.handle.geometry.x
        old_a, old_b = a.handle, b.handle
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(mounted)
        assert flex.handle.geometry.width == 767
        assert a.handle is old_a and b.handle is old_b
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "GridItem", "headless", "interaction", "flex_content",
            "measured_children_readback", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_alternating_grid_flex_grid_uses_cinnamon_at_each_depth(request):
    from psx import Flex
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    scene = Grid(
        GridItem(
            Flex(
                Grid(
                    GridItem(Text("a"), span={"base": 12, "md": 6}, key="a"),
                    GridItem(Text("b"), span={"base": 12, "md": 6}, key="b"),
                    gap=4,
                ),
                direction="column", width="100%", height="80px",
                align_items="stretch",
            ), span=12, key="outer",
        ), gap=4,
    )
    try:
        root = reconciler.render(scene)
        inner = root.children[0].children[0].children[0]
        first = inner.children[0].handle
        second = inner.children[1].handle
        assert first.geometry.width == 398
        for width, expected in ((767, 767), (800, 398), (767, 767)):
            renderer.set_sfle_constraints(viewport(width))
            renderer.commit_layout(root)
            assert first.geometry.width == expected
            assert inner.children[0].handle is first
            assert inner.children[1].handle is second
            assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "alternating_composition",
            "bounded_reflow_identity", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_mixed_headless_grid_siblings_keyed_reorder_preserves_handles(request):
    from psx import Flex
    renderer = make_renderer()
    reconciler = Reconciler(renderer)

    def scene(order):
        return Flex(*(
            Grid(GridItem(Text(label), key="item", span=12),
                 key=label, gap=4)
            for label in order
        ), direction="column", width="100%", height=100,
            align_items="stretch")

    try:
        mounted = reconciler.render(scene(("a", "b")))
        handles = {node.node.key: (node.handle, node.children[0].handle,
                                  node.children[0].children[0].handle)
                   for node in mounted.children}
        changed = reconciler.render(scene(("b", "a")))
        for child in changed.children:
            assert (child.handle, child.children[0].handle,
                    child.children[0].children[0].handle) == handles[child.node.key]
            assert child.children[0].handle.geometry.width == 800
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(changed)
        for child in changed.children:
            assert child.children[0].handle.geometry.width == 767
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "mixed_keyed_siblings",
            "reorder_identity_readback", applicability="partial_native"), True)
    finally:
        reconciler.unmount()


def test_grid_flex_grid_nested_reflow_and_stale_generation_recovery(request):
    """Cinnamon must own all three layout levels, including Headless Flex."""
    from psx import Flex
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    scene = Grid(
        GridItem(Flex(
            Grid(
                GridItem(Text("a"), key="a", span={"base": 12, "md": 6}),
                GridItem(Text("b"), key="b", span={"base": 12, "md": 6}),
                gap=4,
            ), direction="column", width="100%", align_items="stretch",
        ), key="outer", span=12),
        gap=4,
    )
    try:
        mounted = reconciler.render(scene)
        nested = mounted.children[0].children[0].children[0]
        first = nested.children[0].handle
        assert first.geometry.width == 398
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(mounted)
        assert nested.children[0].handle is first
        assert first.geometry.width == 767
        assert renderer.grid_result[1].max_readback_error == 0
        assert_feature(request, Feature(
            "Grid", "headless", "interaction", "grid_flex_grid",
            "nested_reflow_identity", applicability="partial_native"), True)
    finally:
        reconciler.unmount()
