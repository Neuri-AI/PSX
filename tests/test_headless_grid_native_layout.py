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
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "geometry_readback", applicability="native"), True)
    assert_feature(request, Feature("GridItem", "headless", "interaction", "native_child", "geometry_readback", applicability="native"), True)
    reconciler.unmount()
    assert renderer.grid_result is None
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "teardown", applicability="native"), True)


def test_mounted_grid_reflow_and_keyed_reorder_preserve_handles(request):
    renderer = make_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(tree())
    handles = {child.node.key: child.handle for child in root.children}
    renderer.set_sfle_constraints(viewport(767))
    renderer.commit_layout(root)
    assert root.children[0].handle.geometry.width == 767
    assert root.children[1].handle.geometry.y == 14
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "resize_reflow", applicability="native"), True)
    reordered = reconciler.render(tree(("b", "a")))
    assert reordered.children[0].handle is handles["b"]
    assert reordered.children[1].handle is handles["a"]
    assert reordered.children[0].handle.geometry.y == 0
    assert_feature(request, Feature("Grid", "headless", "interaction", "native_root", "keyed_reorder", applicability="native"), True)
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
