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
