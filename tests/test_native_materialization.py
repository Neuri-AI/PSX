from types import SimpleNamespace

from psx.core.hooks import Ref
from psx.core.instance import MountedInstance
from psx.core.native_materialization import (
    finalize_native_materialization,
    synchronize_native_materialization,
)
from psx.core.vnode import NodeKind
from psx.layout.adapters.native_flow_viewport import FlowViewportPlan
from psx.layout.grid.grid_native_plan import GridNativePlacement


class Handle:
    def __init__(self):
        self.widget = object()


class Renderer:
    def __init__(self):
        self.insertions = []
        self.removals = []

    def insert(self, parent, child, index):
        self.insertions.append((parent, child, index))

    def remove(self, parent, child):
        self.removals.append((parent, child))


def instance(parent=None, *, ref=None):
    node = SimpleNamespace(kind=NodeKind.HOST, type="div", props={"ref": ref})
    mounted = MountedInstance(node, parent)
    mounted.handle = Handle()
    mounted.attached = True
    return mounted


def plan(root, deferred):
    placements = (
        GridNativePlacement("card-a", 0, 0, 10, 10, 10, 10, False, False),
        GridNativePlacement("card-a/text", 0, 0, 10, 10, 10, 10, False, False),
        GridNativePlacement("card-b", 0, 20, 10, 10, 10, 10, False, False),
    )
    return FlowViewportPlan(
        None, ("card-a", "card-b"), placements,
        {"card-a": root.children[0].handle,
         "card-a/text": root.children[0].children[0].handle,
         "card-b": root.children[1].handle},
        100, 1, "test", frozenset(deferred),
    )


def test_p2_detaches_only_after_a_successful_native_commit():
    renderer = Renderer()
    root = instance()
    first, second = instance(root), instance(root)
    leaf = instance(first)
    root.children = [first, second]
    first.children = [leaf]
    candidate = synchronize_native_materialization(renderer, root, plan(root, {"card-a", "card-a/text"}).widgets,
                                                    plan(root, {"card-a", "card-a/text"}))
    assert not renderer.removals
    accepted = finalize_native_materialization(renderer, root, candidate.widgets, candidate)
    assert accepted.deferred_ids == frozenset({"card-a", "card-a/text"})
    assert renderer.removals == [(root.handle, first.handle)]
    assert not first.native_materialized
    assert first.hooks == []  # Logical state was never unmounted.


def test_visible_group_reactivates_and_a_ref_pins_only_its_group():
    renderer = Renderer()
    root = instance()
    first, second = instance(root), instance(root, ref=Ref())
    leaf = instance(first)
    root.children = [first, second]
    first.children = [leaf]
    candidate = synchronize_native_materialization(renderer, root, plan(root, {"card-a", "card-a/text", "card-b"}).widgets,
                                                    plan(root, {"card-a", "card-a/text", "card-b"}))
    accepted = finalize_native_materialization(renderer, root, candidate.widgets, candidate)
    assert accepted.deferred_ids == frozenset({"card-a", "card-a/text"})
    assert renderer._psx_native_materialization_pins["native-ref"] == 1
    visible = synchronize_native_materialization(renderer, root, plan(root, set()).widgets, plan(root, set()))
    assert not visible.deferred_ids
    assert renderer.insertions == [(root.handle, first.handle, 0)]
    assert first.native_materialized
