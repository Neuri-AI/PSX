"""Mounted Fast Refresh must retain native widget identity on each backend."""
from __future__ import annotations

import os
from types import SimpleNamespace

from psx import App, Flex, Text, component, use_state
from psx.devtools import coordinated_refresh as refresh
from tests.test_mounted_grid_native_renderers import make_renderer


class Example:
    def render(self):
        raise AssertionError("The original render is replaced by authored source")


def _native_text(widget, backend: str) -> str:
    if backend == "qt":
        return widget.text()
    if backend == "tk":
        return widget.cget("text")
    return widget.text


def test_compatible_refresh_keeps_native_window_label_and_hook_state(monkeypatch, tmp_path):
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    source = tmp_path / "main.py"
    source.write_text("class Example: pass\n", encoding="utf-8")
    context = Example()

    def render_before(self):
        state, _ = use_state(17)
        return Flex(Text(f"before:{state}"))

    def render_after(self):
        state, _ = use_state(17)
        return Flex(Text(f"after:{state}"))

    holder = [render_before]

    def root():
        return holder[0](context)

    definition = component(root)
    context._development_render = holder
    context._development_root_definition = definition
    context.app = App(definition, renderer=renderer)
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    monkeypatch.setattr(
        refresh, "_load_updated_class",
        lambda *_: SimpleNamespace(render=render_after),
    )
    try:
        context.app.mount()
        original_host = context.app.reconciler.root.native_handle()
        original_label = context.app.reconciler.root.children[0].children[0].handle.widget
        assert _native_text(original_label, backend) == "before:17"
        assert refresh.refresh_context_source(context, source, ("main.py",))
        after_host = context.app.reconciler.root.native_handle()
        after_label = context.app.reconciler.root.children[0].children[0].handle.widget
        assert after_host is original_host
        assert after_label is original_label
        assert _native_text(after_label, backend) == "after:17"
    finally:
        context.app.unmount()
        close()
