"""Logical component identity survives destruction of native resources."""
import pytest

from psx import Button, Flex, Text, component, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer, HeadlessHandle


class LifecycleRenderer(HeadlessRenderer):
    """Native ownership port; geometry is covered by layout integration tests."""

    def _adapter_create(self, node, parent):
        if node.type == "Flex":
            handle = HeadlessHandle(node.type, dict(node.props))
            self.operations.append(("create", handle))
            return handle
        return super()._adapter_create(node, parent)


def test_suspended_component_keeps_hook_cells_and_projects_latest_description():
    renderer = LifecycleRenderer()
    reconciler = Reconciler(renderer)
    setters = []

    @component
    def Card():
        value, setter = use_state(3)
        setters.append(setter)
        return Text(str(value))

    root = reconciler.render(Flex(Card(key="card"), Text("sibling", key="sibling")))
    card, sibling = root.children
    cells = tuple(card.hooks)
    prior = card.native_handle()
    sibling_handle = sibling.handle
    reconciler._suspend_native(card)
    assert {id(node) for node in reconciler._native_instances.values()} == {
        id(root), id(sibling)}
    assert prior.destroyed
    assert card.children[0].handle is None
    assert not card.disposed
    assert tuple(card.hooks) == cells
    renderer.operations.clear()
    # Logical reconciliation may change component output without allocating
    # or updating any native object within the suspended card.
    setters[-1](8)
    renderer.flush()
    assert card.children[0].node.props["value"] == "8"
    assert card.children[0].handle is None
    assert not any(op[0] == "create" for op in renderer.operations)
    reconciler._resume_native(card)
    assert reconciler._native_instances[id(card.children[0])] is card.children[0]
    assert card.native_handle() is not prior
    assert card.native_handle().props["value"] == "8"
    assert tuple(card.hooks) == cells
    assert sibling.handle is sibling_handle
    assert root.handle.children == [card.native_handle(), sibling_handle]
    reconciler.unmount()
    assert not reconciler._native_instances


def test_suspended_keyed_children_can_change_without_native_work():
    renderer = LifecycleRenderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(Flex(Text("old", key="old"), key="card")))
    card = root.children[0]
    reconciler._suspend_native(card)
    renderer.operations.clear()
    reconciler.render(Flex(Flex(Text("new", key="new"), key="card")))
    assert card.children[0].handle is None
    assert card.children[0].native_suspended
    assert not renderer.operations
    reconciler._resume_native(card)
    assert card.handle.children[0].props["value"] == "new"
    reconciler.unmount()


def test_activation_failure_releases_partial_handles_without_disposing_logic(monkeypatch):
    renderer = LifecycleRenderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(Flex(Text("one"), Text("two"), key="card")))
    card = root.children[0]
    reconciler._suspend_native(card)
    create = renderer.create
    created = []

    def failing(node, parent):
        if node.props.get("value") == "two":
            raise RuntimeError("creation failed")
        handle = create(node, parent)
        created.append(handle)
        return handle

    monkeypatch.setattr(renderer, "create", failing)
    with pytest.raises(RuntimeError, match="creation failed"):
        reconciler._resume_native(card)
    assert all(handle.destroyed for handle in created)
    assert not card.disposed
    assert card.handle is None
    assert card.native_suspended
    assert set(reconciler._native_instances) == {id(root)}
    monkeypatch.setattr(renderer, "create", create)
    reconciler._resume_native(card)
    assert len(card.handle.children) == 2
    reconciler.unmount()
