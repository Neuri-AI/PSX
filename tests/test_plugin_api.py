from __future__ import annotations

import pytest

from psx import (
    ComponentRegistry,
    Text,
    load_plugins,
    psx,
    register_component,
    renderer_capabilities,
)
from psx.core.errors import DuplicateComponentError
from psx.renderers.adapters import DelegatingAdapter
from psx.renderers.headless import HeadlessRenderer


class BadgePlugin:
    def register(self, api) -> None:
        api.component("Badge", lambda label, key=None: Text(label, key=key))
        api.adapter("headless", "Badge", DelegatingAdapter())


def test_external_plugin_registers_namespaced_markup_component_and_adapter() -> None:
    registry = ComponentRegistry()
    renderer = HeadlessRenderer()
    loaded = load_plugins(registry, renderers={"headless": renderer}, plugins=[BadgePlugin()], namespace="sample")
    assert loaded[0].__class__ is BadgePlugin
    assert psx('<sample.Badge label="new" />', registry=registry).type is not None
    assert "sample.Badge" in renderer_capabilities(renderer).components


def test_plugin_conflicts_and_registries_are_isolated() -> None:
    first, second = ComponentRegistry(), ComponentRegistry()
    register_component(first, "Badge", Text, namespace="sample")
    with pytest.raises(DuplicateComponentError):
        register_component(first, "Badge", Text, namespace="sample")
    register_component(second, "Badge", Text, namespace="other")
    assert second.contains("other.Badge") and not second.contains("sample.Badge")


def test_entry_point_discovery_is_opt_in_and_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class Point:
        def load(self):
            calls.append("load")
            return BadgePlugin

    class Points:
        def select(self, *, group: str):
            assert group == "tests.psx.plugins"
            return (Point(),)

    monkeypatch.setattr("psx.plugins.metadata.entry_points", lambda: Points())
    registry = ComponentRegistry()
    load_plugins(registry)
    assert calls == []
    load_plugins(
        registry,
        renderers={"headless": HeadlessRenderer()},
        discover=True,
        group="tests.psx.plugins",
        namespace="entry",
    )
    assert calls == ["load"] and registry.contains("entry.Badge")


def test_plugin_api_reports_native_capability_without_gui_imports() -> None:
    caps = renderer_capabilities(HeadlessRenderer())
    assert caps.supports_native and {"Text", "Native"} <= caps.components
