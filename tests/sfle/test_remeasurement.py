"""Regression fixtures for pure F2.2.4.5 dependency invalidation."""
import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection
from psx.sfle.remeasurement import plan_remeasurement
from psx.sfle.used_size_tree import UsedSizeTree


def size(width, height=20):
    return LayoutConstraints(AvailableSize(width, width is not None), AvailableSize(height, height is not None))


def snapshot():
    return LayoutInput(1, 8, WritingDirection.LTR, size(200), (
        LayoutNode("root", None, "Flex", ()),
        LayoutNode("child", "root", "Flex", ()),
        LayoutNode("leaf", "child", "Text", ()),
    ), ())


def tree(generation=8, child=100, leaf=50):
    return UsedSizeTree(generation, (
        ("root", size(200)), ("child", size(child)), ("leaf", size(leaf)),
    ), ())


def test_changed_child_invalidates_descendants_and_ancestors():
    delta = plan_remeasurement(snapshot(), tree(7), tree(child=120))
    assert delta.changed == ("child",)
    assert delta.remeasure == ("leaf", "child", "root")


def test_unchanged_constraints_produce_no_remeasure():
    delta = plan_remeasurement(snapshot(), tree(7), tree())
    assert delta.changed == ()
    assert delta.remeasure == ()


def test_unknown_axis_stays_deferred():
    delta = plan_remeasurement(snapshot(), tree(7), tree(child=None))
    assert delta.deferred == ("child",)
    assert delta.remeasure == ("leaf", "child", "root")


def test_generation_and_node_order_are_validated():
    with pytest.raises(SFLEError):
        plan_remeasurement(snapshot(), tree(9), tree())
    with pytest.raises(SFLEError):
        plan_remeasurement(snapshot(), tree(7), UsedSizeTree(8, (
            ("root", size(200)), ("leaf", size(50)), ("child", size(100)),
        ), ()))
