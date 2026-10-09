"""Renderer-local component adapters and their isolated registries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.vnode import NodeKind, VNode


class ComponentAdapter(Protocol):
    """Native lifecycle operations for one PSX component in one renderer.

    Optional child-lifecycle hooks (must be discovered via ``getattr``, never
    called directly on the adapter object)::

        insert(self, renderer, parent, child, index) -> bool
        move(self, renderer, parent, child, index) -> bool
        remove(self, renderer, parent, child) -> bool

    Returning True means the adapter handled the operation and the renderer
    must not run its default. Returning False (or not implementing the hook)
    lets the renderer handle it. Existing and third-party adapters are free to
    omit these; renderers must probe with ``getattr``.
    """

    def create(self, renderer: object, node: VNode, parent: object | None) -> object: ...
    def update(self, renderer: object, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None: ...
    def bind_event(self, renderer: object, handle: object, event: str, slot: EventSlot) -> object: ...
    def unbind_event(self, renderer: object, subscription: object) -> None: ...
    def destroy(self, renderer: object, handle: object) -> None: ...


class RendererAdapterRegistry:
    """Instance-scoped adapter lookup; no GUI or global state is required."""

    def __init__(self) -> None:
        self._adapters: dict[str, ComponentAdapter] = {}

    def register(self, component: str, adapter: ComponentAdapter, *, replace: bool = False) -> None:
        if not isinstance(component, str) or not component:
            raise ValueError("Adapter component names must be non-empty strings.")
        if component in self._adapters and not replace:
            raise ValueError(f"An adapter is already registered for {component!r}.")
        self._adapters[component] = adapter

    def resolve(self, component: str) -> ComponentAdapter:
        try:
            return self._adapters[component]
        except KeyError as error:
            raise RendererCapabilityError(f"No adapter is registered for component {component!r}.") from error

    def get(self, component: str) -> ComponentAdapter | None:
        return self._adapters.get(component)

    def snapshot(self) -> Mapping[str, ComponentAdapter]:
        return dict(self._adapters)


@dataclass(frozen=True, slots=True)
class DelegatingAdapter:
    """Adapter used while extracting a renderer's legacy lifecycle methods."""

    def create(self, renderer: object, node: VNode, parent: object | None) -> object:
        return renderer._adapter_create(node, parent)  # type: ignore[attr-defined]

    def update(self, renderer: object, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        renderer._adapter_update(handle, changed, removed)  # type: ignore[attr-defined]

    def bind_event(self, renderer: object, handle: object, event: str, slot: EventSlot) -> object:
        return renderer._adapter_bind_event(handle, event, slot)  # type: ignore[attr-defined]

    def unbind_event(self, renderer: object, subscription: object) -> None:
        renderer._adapter_unbind_event(subscription)  # type: ignore[attr-defined]

    def destroy(self, renderer: object, handle: object) -> None:
        renderer._adapter_destroy(handle)  # type: ignore[attr-defined]

    def insert(self, renderer: object, parent: object, child: object, index: int) -> bool:
        return False

    def move(self, renderer: object, parent: object, child: object, index: int) -> bool:
        return False

    def remove(self, renderer: object, parent: object, child: object) -> bool:
        return False

def adapter_key(node: VNode) -> str:
    return "Native" if node.kind is NodeKind.NATIVE else str(node.type)


def handle_adapter_key(handle: object) -> str:
    node_type = getattr(handle, "node_type", getattr(handle, "type", None))
    return "Native" if not isinstance(node_type, str) else node_type


@dataclass(frozen=True, slots=True)
class AdapterSubscription:
    adapter: ComponentAdapter
    subscription: object

def run_child_hook(adapter: object, name: str, renderer: object, *args: object) -> bool:
    """Invoke an optional child-lifecycle hook. Returns False if absent."""
    hook = getattr(adapter, name, None)
    if hook is None:
        return False
    return bool(hook(renderer, *args))