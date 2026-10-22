"""Source refresh honors component identity, UI ownership and rollback."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from psx.core.vnode import NodeKind
from psx.devtools import coordinated_refresh as refresh


class FakeReconciler:
    def __init__(self, root, *, compatible=True):
        self.root = root
        self.compatible = compatible
        self.calls = []

    def try_reevaluate(self, instance):
        self.calls.append(instance)
        return self.compatible


def make_context(source, compatible=True):
    original = lambda self: "old"
    definition = object()
    instance = SimpleNamespace(
        node=SimpleNamespace(kind=NodeKind.COMPONENT, type=definition),
        children=[],
    )
    reconciler = FakeReconciler(instance, compatible=compatible)
    context = SimpleNamespace(
        app=SimpleNamespace(reconciler=reconciler),
        _development_root_definition=definition,
        _development_render=[original],
    )
    return context, reconciler, original


def test_source_edit_rebinds_render_and_preserves_mounted_boundary(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    context, reconciler, original = make_context(entry)
    candidate = lambda self: "updated"
    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *args: SimpleNamespace(render=candidate))
    assert refresh.refresh_context_source(context, entry, ("main.py",)) is True
    assert context._development_render[0] is candidate
    assert reconciler.calls == [reconciler.root]
    assert context._development_render[0] is not original


def test_hook_incompatibility_restores_previous_render(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    context, reconciler, original = make_context(entry, compatible=False)
    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *args: SimpleNamespace(render=lambda self: "new"))
    assert refresh.refresh_context_source(context, entry, ("main.py",)) is False
    assert context._development_render[0] is original
    assert reconciler.calls == [reconciler.root]


def test_syntax_failure_preserves_last_working_callable(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("this is not valid Python(", encoding="utf-8")
    context, reconciler, original = make_context(entry)
    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    def fail(*args):
        raise SyntaxError("source invalid")
    monkeypatch.setattr(refresh, "_load_updated_class", fail)
    with pytest.raises(SyntaxError):
        refresh.refresh_context_source(context, entry, ("main.py",))
    assert context._development_render[0] is original
    assert reconciler.calls == []


def test_css_refresh_reevaluates_without_replacing_render(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    context, reconciler, original = make_context(entry)
    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    assert refresh.refresh_context_source(context, entry, ("styles/theme.css",)) is True
    assert reconciler.calls == [reconciler.root]
    assert context._development_render[0] is original


def test_project_boundary_rejects_path_escape(tmp_path):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    context, _, previous = make_context(entry)
    with pytest.raises(ValueError, match="outside"):
        refresh.refresh_context_source(context, entry, ("../outside.py",))
    assert context._development_render[0] is previous


def test_unrelated_file_does_not_trigger_refresh(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    context, reconciler, original = make_context(entry)
    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    assert refresh.refresh_context_source(context, entry, ("unrelated.json",)) is False
    assert reconciler.calls == []
    assert context._development_render[0] is original


def test_real_headless_component_refresh_preserves_native_handle_and_hook_state(
    tmp_path, monkeypatch
):
    from psx import App, Flex, Text, component, use_state
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    prefix = ["before"]

    def render(_ctx):
        count, _ = use_state(7)
        return Flex(Text(f"{prefix[0]}:{count}"))

    class Demo:
        pass

    holder = [render]
    def root():
        return holder[0](context)

    definition = component(root)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )
    app = App(definition, renderer=renderer)
    context = SimpleNamespace(
        app=app, _development_root_definition=definition, _development_render=holder,
    )
    app.mount()
    original = app.reconciler.root.native_handle()
    assert original.children[0].props["value"] == "before:7"

    def updated(_ctx):
        count, _ = use_state(7)
        return Flex(Text(f"after:{count}"))

    monkeypatch.setattr(refresh, "_reload_policy", lambda host: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *args: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *args: SimpleNamespace(render=updated))
    try:
        assert refresh.refresh_context_source(context, entry, ("main.py",))
        assert app.reconciler.root.native_handle() is original
        assert original.children[0].props["value"] == "after:7"
    finally:
        app.unmount()
