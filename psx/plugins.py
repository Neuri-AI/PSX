"""Public, dependency-free extension API for third-party PSX libraries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
from typing import Protocol

from .core.contracts import ComponentContract
from .core.registry import ComponentConstructor, ComponentDefinition, ComponentRegistry
from .renderers.adapters import ComponentAdapter, RendererAdapterRegistry

PLUGIN_ENTRY_POINT_GROUP = "psx.plugins"


@dataclass(frozen=True, slots=True)
class RendererCapabilities:
    """The adapters available on one concrete renderer instance."""

    name: str
    components: frozenset[str]
    supports_native: bool


def qualify(namespace: str | None, name: str) -> str:
    """Build a markup-safe external component name such as ``acme.Badge``."""
    if not isinstance(name, str) or not name:
        raise ValueError("Component names must be non-empty strings.")
    if namespace is None:
        return name
    if not isinstance(namespace, str) or not namespace or any(not part for part in namespace.split(".")):
        raise ValueError("Plugin namespaces must be dot-separated non-empty names.")
    return f"{namespace}.{name}"


def register_component(
    registry: ComponentRegistry,
    name: str,
    constructor: ComponentConstructor,
    *,
    namespace: str | None = None,
    contract: ComponentContract | None = None,
) -> ComponentDefinition:
    """Register an external component in one registry without global state."""
    return registry.register(qualify(namespace, name), constructor, contract=contract)


def register_adapter(
    renderer: object,
    component: str,
    adapter: ComponentAdapter,
    *,
    replace: bool = False,
) -> None:
    """Register an adapter through a renderer's public extension seam."""
    method = getattr(renderer, "register_adapter", None)
    if not callable(method):
        raise TypeError("Renderer does not expose register_adapter().")
    method(component, adapter, replace=replace)


def renderer_capabilities(renderer: object) -> RendererCapabilities:
    """Return instance-specific adapter capabilities without importing a GUI binding."""
    adapters = getattr(renderer, "adapters", None)
    if not isinstance(adapters, RendererAdapterRegistry):
        raise TypeError("Renderer does not expose a RendererAdapterRegistry.")
    components = frozenset(adapters.snapshot())
    return RendererCapabilities(
        name=type(renderer).__name__, components=components, supports_native="Native" in components
    )


class Plugin(Protocol):
    """Protocol implemented by an external package's plugin object."""

    def register(self, api: "PluginAPI") -> None: ...


@dataclass(slots=True)
class PluginAPI:
    """Scoped API passed to a plugin; it never owns global registries."""

    registry: ComponentRegistry
    renderers: Mapping[str, object]
    namespace: str | None = None

    def component(
        self, name: str, constructor: ComponentConstructor, *, contract: ComponentContract | None = None
    ) -> ComponentDefinition:
        return register_component(self.registry, name, constructor, namespace=self.namespace, contract=contract)

    def adapter(self, renderer: str, component: str, adapter: ComponentAdapter, *, replace: bool = False) -> None:
        try:
            target = self.renderers[renderer]
        except KeyError as error:
            raise KeyError(f"Plugin requested unknown renderer {renderer!r}.") from error
        register_adapter(target, qualify(self.namespace, component), adapter, replace=replace)

    def capabilities(self, renderer: str) -> RendererCapabilities:
        try:
            return renderer_capabilities(self.renderers[renderer])
        except KeyError as error:
            raise KeyError(f"Plugin requested unknown renderer {renderer!r}.") from error


def load_plugins(
    registry: ComponentRegistry,
    *,
    renderers: Mapping[str, object] | None = None,
    plugins: Iterable[Plugin | object] = (),
    discover: bool = False,
    group: str = PLUGIN_ENTRY_POINT_GROUP,
    namespace: str | None = None,
) -> tuple[Plugin, ...]:
    """Register explicit plugins and, optionally, ``importlib.metadata`` entry points.

    Discovery is opt-in. Entry points are loaded only here, preserving lazy GUI
    imports for normal PSX use. Component and adapter conflicts propagate from
    their existing registries rather than being silently overwritten.
    """
    candidates = list(plugins)
    if discover:
        entry_points = metadata.entry_points()
        selected = entry_points.select(group=group) if hasattr(entry_points, "select") else entry_points.get(group, ())
        candidates.extend(point.load() for point in selected)
    api = PluginAPI(registry, dict(renderers or {}), namespace)
    loaded: list[Plugin] = []
    for candidate in candidates:
        plugin = _plugin_instance(candidate)
        plugin.register(api)
        loaded.append(plugin)
    return tuple(loaded)


def _plugin_instance(candidate: Plugin | object) -> Plugin:
    plugin = candidate
    if isinstance(plugin, type):
        plugin = plugin()
    elif not callable(getattr(plugin, "register", None)) and callable(plugin):
        plugin = plugin()
    if not callable(getattr(plugin, "register", None)):
        raise TypeError("PSX plugins must expose register(api).")
    return plugin  # type: ignore[return-value]
