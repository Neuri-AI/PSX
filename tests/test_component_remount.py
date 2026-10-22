"""Incompatible hook updates replace only the affected component boundary."""
from types import SimpleNamespace

import pytest

from psx import App, Flex, Text, component, use_effect, use_ref, use_state
from psx.devtools import coordinated_refresh as refresh
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints


def renderer():
    return HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )


def mounted(source, before):
    class Context:
        pass
    context = Context()
    holder = [before]
    def root():
        return holder[0](context)
    definition = component(root)
    app = App(definition, renderer=renderer())
    context.app = app
    context._development_root_definition = definition
    context._development_render = holder
    app.mount()
    return context


def invoke(context, source, updated, monkeypatch):
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class", lambda *_: SimpleNamespace(render=updated))
    return refresh.refresh_context_source(context, source, ("main.py",))


def test_added_hook_remounts_boundary_but_keeps_native_flex_and_text(tmp_path, monkeypatch):
    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    old_setters = []
    def before(_):
        value, setter = use_state("old")
        old_setters.append(setter)
        return Flex(Text(value))
    def after(_):
        value, _ = use_state("new")
        use_ref()
        return Flex(Text(value))
    context = mounted(source, before)
    try:
        first_instance = context.app.reconciler.root
        native = first_instance.native_handle()
        label = native.children[0]
        assert invoke(context, source, after, monkeypatch)
        assert context.app.reconciler.root is not first_instance
        assert first_instance.disposed
        assert context.app.reconciler.root.native_handle() is native
        assert native.children[0] is label
        assert label.props["value"] == "new"
        old_setters[0]("stale")
        context.app.renderer.flush()
        assert label.props["value"] == "new"
    finally:
        context.app.unmount()


def test_removed_hook_releases_effects_and_reuses_widget(tmp_path, monkeypatch):
    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    events = []
    def before(_):
        use_state("state")
        use_effect(lambda: (events.append("start"), lambda: events.append("stop"))[1], [])
        return Flex(Text("before"))
    def after(_):
        use_state("fresh")
        return Flex(Text("after"))
    context = mounted(source, before)
    try:
        native = context.app.reconciler.root.native_handle()
        assert events == ["start"]
        assert invoke(context, source, after, monkeypatch)
        assert events == ["start", "stop"]
        assert context.app.reconciler.root.native_handle() is native
        assert native.children[0].props["value"] == "after"
    finally:
        context.app.unmount()
    assert events == ["start", "stop"]


def test_invalid_candidate_does_not_unmount_existing_boundary(tmp_path, monkeypatch):
    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    def before(_):
        return Flex(Text("safe"))
    def invalid(_):
        use_state(2)
        raise ValueError("invalid candidate")
    context = mounted(source, before)
    original = context.app.reconciler.root
    try:
        with pytest.raises(ValueError, match="invalid candidate"):
            invoke(context, source, invalid, monkeypatch)
        assert context.app.reconciler.root is original
        assert not original.disposed
        assert original.native_handle().children[0].props["value"] == "safe"
    finally:
        context.app.unmount()


def test_cleanup_failure_still_disposes_previous_hook_slots(tmp_path, monkeypatch):
    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    def failing_cleanup():
        raise RuntimeError("cleanup failed")
    def before(_):
        use_effect(lambda: failing_cleanup, [])
        use_state(1)
        return Flex(Text("before"))
    def after(_):
        use_ref()
        return Flex(Text("after"))
    context = mounted(source, before)
    previous = context.app.reconciler.root
    try:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            invoke(context, source, after, monkeypatch)
        assert previous.disposed
        assert previous.hooks == []
        assert context.app.reconciler.root is not previous
        assert context.app.reconciler.root.native_handle().children[0].props["value"] == "after"
    finally:
        context.app.unmount()


def test_nested_hook_change_remounts_only_child_and_preserves_sibling(tmp_path, monkeypatch):
    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    mode = ["before"]
    old_setters = []

    @component
    def Child():
        state, setter = use_state(19)
        if mode[0] == "before":
            old_setters.append(setter)
        else:
            use_ref()
        return Flex(Text(f"{mode[0]}:{state}"))

    def before(_):
        return Flex(Child(), Text("independent"))

    def after(_):
        mode[0] = "after"
        return Flex(Child(), Text("independent"))

    context = mounted(source, before)
    try:
        root = context.app.reconciler.root
        parent_flex = root.children[0]
        old_child = parent_flex.children[0]
        sibling = parent_flex.children[1]
        host = root.native_handle()
        sibling_widget = sibling.handle
        child_widget = old_child.native_handle()
        assert invoke(context, source, after, monkeypatch)
        new_root = context.app.reconciler.root
        assert new_root is root
        assert new_root.native_handle() is host
        assert parent_flex.children[1] is sibling
        assert sibling.handle is sibling_widget
        assert parent_flex.children[0] is not old_child
        assert old_child.disposed
        assert parent_flex.children[0].native_handle() is child_widget
        old_setters[0]("stale")
        context.app.renderer.flush()
        assert parent_flex.children[0].children[0].children[0].handle.props["value"] == "after:19"
    finally:
        context.app.unmount()
