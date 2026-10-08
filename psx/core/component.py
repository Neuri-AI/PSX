"""Function component declarations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from .vnode import Key, VNode, create_element


@dataclass(slots=True)
class ComponentType:
    """Stable component definition; calling it describes a component VNode."""

    render: Callable[..., object]
    name: str

    def __call__(self, *children: object, key: Key | None = None, **props: object) -> VNode:
        if children:
            props["children"] = children
        return create_element(self, key=key, **props)

    def __repr__(self) -> str:
        return f"ComponentType({self.name})"


_COMPONENT_REGISTRY: dict[tuple[str, str], ComponentType] = {}


def component(function: Callable[..., object]) -> ComponentType:
    """Declare a component, preserving identity across a compatible reload.

    The registry is keyed by Python's module and qualified name. A reload
    replaces the render function of an already-mounted definition; devtools
    later schedules that boundary through the normal reconciler. Ordinary
    component declarations retain the same public API.
    """
    key = (function.__module__, function.__qualname__)
    existing = _COMPONENT_REGISTRY.get(key)
    if existing is not None:
        existing.render = function
        existing.name = function.__name__
        return existing
    definition = ComponentType(function, function.__name__)
    _COMPONENT_REGISTRY[key] = definition
    return definition
