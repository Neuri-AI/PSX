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


def test_incompatible_hooks_remount_only_boundary_and_preserve_native_widget(monkeypatch, tmp_path):
    from psx import use_ref

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    source = tmp_path / "main.py"
    source.write_text("class Example: pass\n", encoding="utf-8")
    context = Example()

    def render_before(self):
        state, _ = use_state(13)
        return Flex(Text(f"before:{state}"))

    def render_after(self):
        state, _ = use_state(13)
        use_ref()
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
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *_: SimpleNamespace(render=render_after))
    try:
        context.app.mount()
        old_boundary = context.app.reconciler.root
        old_host = old_boundary.native_handle()
        old_label = old_boundary.children[0].children[0].handle.widget
        assert refresh.refresh_context_source(context, source, ("main.py",))
        assert context.app.reconciler.root is not old_boundary
        assert old_boundary.disposed
        assert context.app.reconciler.root.native_handle() is old_host
        assert context.app.reconciler.root.children[0].children[0].handle.widget is old_label
        assert _native_text(old_label, backend) == "after:13"
    finally:
        context.app.unmount()
        close()


def test_nested_incompatible_component_preserves_native_sibling(monkeypatch, tmp_path):
    from psx import use_ref

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    source = tmp_path / "main.py"
    source.write_text("class Example: pass\n", encoding="utf-8")
    context = Example()
    updated = [False]

    @component
    def Child():
        count, _ = use_state(11)
        if updated[0]:
            use_ref()
        return Flex(Text(f"{'after' if updated[0] else 'before'}:{count}"))

    def render_before(self):
        return Flex(Child(), Text("independent"))

    def render_after(self):
        updated[0] = True
        return Flex(Child(), Text("independent"))

    holder = [render_before]
    def root():
        return holder[0](context)

    definition = component(root)
    context._development_render = holder
    context._development_root_definition = definition
    context.app = App(definition, renderer=renderer)
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *_: SimpleNamespace(render=render_after))
    try:
        context.app.mount()
        parent = context.app.reconciler.root.children[0]
        previous_child = parent.children[0]
        independent = parent.children[1].handle.widget
        child_widget = previous_child.native_handle().widget
        assert refresh.refresh_context_source(context, source, ("main.py",))
        assert previous_child.disposed
        assert parent.children[0] is not previous_child
        assert parent.children[0].native_handle().widget is child_widget
        assert parent.children[1].handle.widget is independent
        assert _native_text(independent, backend) == "independent"
        inner_text = parent.children[0].children[0].children[0].handle.widget
        assert _native_text(inner_text, backend) == "after:11"
    finally:
        context.app.unmount()
        close()


def test_repeated_refresh_invalid_save_and_recovery_retains_native_identity(monkeypatch, tmp_path):
    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    source = tmp_path / "main.py"
    source.write_text("class Example: pass\n", encoding="utf-8")
    context = Example()
    def render_before(self):
        state, _ = use_state(23)
        return Flex(Text(f"cycle:0:{state}"))
    holder = [render_before]
    def root():
        return holder[0](context)
    definition = component(root)
    context._development_render = holder
    context._development_root_definition = definition
    context.app = App(definition, renderer=renderer)
    replacement = [render_before]
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    monkeypatch.setattr(
        refresh, "_load_updated_class",
        lambda *_: SimpleNamespace(render=replacement[0]),
    )
    try:
        context.app.mount()
        host = context.app.reconciler.root.native_handle()
        label = context.app.reconciler.root.children[0].children[0].handle.widget
        for iteration in range(1, 31):
            def render_next(self, index=iteration):
                state, _ = use_state(23)
                return Flex(Text(f"cycle:{index}:{state}"))
            replacement[0] = render_next
            if iteration % 7 == 0:
                source.write_text("def broken(:\n", encoding="utf-8")
                assert not refresh.refresh_context_source(context, source, ("main.py",))
                assert context.app.reconciler.root.native_handle() is host
            source.write_text("class Example: pass\n", encoding="utf-8")
            assert refresh.refresh_context_source(context, source, ("main.py",))
            assert context.app.reconciler.root.native_handle() is host
            current = context.app.reconciler.root.children[0].children[0].handle.widget
            assert current is label
            assert _native_text(current, backend) == f"cycle:{iteration}:23"
    finally:
        context.app.unmount()
        close()
