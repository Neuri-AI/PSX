from __future__ import annotations

from collections.abc import Mapping

import pytest

from psx import Button, Text, create_element
from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.reconcile import Reconciler
from psx.core.vnode import VNode
from psx.renderers.adapters import ComponentAdapter, DelegatingAdapter, RendererAdapterRegistry
from psx.renderers.headless import HeadlessRenderer


class CountingAdapter:
    def __init__(self) -> None:
        self.delegate = DelegatingAdapter()
        self.calls: list[str] = []

    def create(self, renderer: object, node: VNode, parent: object | None) -> object:
        self.calls.append("create")
        return self.delegate.create(renderer, node, parent)

    def update(self, renderer: object, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        self.calls.append("update")
        self.delegate.update(renderer, handle, changed, removed)

    def bind_event(self, renderer: object, handle: object, event: str, slot: EventSlot) -> object:
        self.calls.append("bind")
        return self.delegate.bind_event(renderer, handle, event, slot)

    def unbind_event(self, renderer: object, subscription: object) -> None:
        self.calls.append("unbind")
        self.delegate.unbind_event(renderer, subscription)

    def destroy(self, renderer: object, handle: object) -> None:
        self.calls.append("destroy")
        self.delegate.destroy(renderer, handle)


def test_adapter_registry_detects_conflicts_and_unknown_components() -> None:
    registry = RendererAdapterRegistry()
    adapter: ComponentAdapter = DelegatingAdapter()
    registry.register("Text", adapter)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("Text", adapter)
    with pytest.raises(RendererCapabilityError, match="No adapter"):
        registry.resolve("Missing")


def test_registered_adapter_owns_component_lifecycle_without_reconciler_changes() -> None:
    renderer = HeadlessRenderer()
    adapter = CountingAdapter()
    renderer.register_adapter("Button", adapter, replace=True)
    reconciler = Reconciler(renderer)
    calls: list[str] = []

    root = reconciler.render(Button("Save", on_click=lambda: calls.append("old")))
    handle = root.handle
    handle.events["on_click"].invoke()
    reconciler.render(Button("Save", on_click=lambda: calls.append("new")))
    assert reconciler.root.handle is handle
    handle.events["on_click"].invoke()
    reconciler.unmount()

    assert calls == ["old", "new"]
    assert adapter.calls == ["create", "bind", "unbind", "destroy"]


def test_custom_host_adapter_can_mount_update_and_unmount() -> None:
    renderer = HeadlessRenderer()
    adapter = CountingAdapter()
    renderer.register_adapter("Badge", adapter)
    reconciler = Reconciler(renderer)

    node = create_element("Badge", value="one", key="badge")
    handle = reconciler.render(node).handle
    reconciler.render(create_element("Badge", value="two", key="badge"))
    assert reconciler.root.handle is handle
    assert handle.props["value"] == "two"
    reconciler.unmount()
    assert adapter.calls == ["create", "update", "destroy"]
