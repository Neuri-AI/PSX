"""Real Headless renderer assertions for admitted portable surface."""
from __future__ import annotations

import pytest

from psx import Button, Flex, Text
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature


@pytest.fixture
def headless_tree():
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(400, True),
                                           AvailableSize(120, True)),
        engine=PythonLayoutEngine())
    tree = Reconciler(renderer)
    try:
        yield renderer, tree
    finally:
        tree.unmount()


@pytest.mark.parametrize(("name", "before", "after", "prop"),
                         [
                             ("Button", "Before", "After", "label"),
                             ("Text", "Before", "After", "value"),
                         ])
def test_admitted_headless_control_reconciliation(headless_tree, request,
                                                  name, before, after, prop):
    renderer, tree = headless_tree

    def view(value):
        options = {"key": "value", "layout_width": "160px",
                   "layout_height": "32px", "flex_basis": "160px", "flex_shrink": 0}
        child = Button(value, **options) if name == "Button" else Text(value, **options)
        return Flex(child, width="400px", height="120px",
                    align_items="flex-start")
    original = tree.render(view(before))
    handle = original.children[0].handle
    assert handle.props[prop] == before
    updated = tree.render(view(after))
    assert updated.children[0].handle is handle
    assert_feature(request, Feature(name, "headless", "property", prop,
                                    "live_update", applicability="native"),
                   handle.props[prop] == after)
    assert_feature(request, Feature(name, "headless", "property", prop,
                                    "native_readback", applicability="native"),
                   handle.props[prop] == after)
    assert renderer.sfle_result.geometry_commit_error == 0
