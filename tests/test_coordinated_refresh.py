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
        self.renderer = SimpleNamespace(commit_layout=lambda root: None)
        self.scheduler = SimpleNamespace(run_effects=lambda: None)

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


class ExternalExample:
    def render(self):
        raise RuntimeError("Source candidate not yet loaded")


def test_real_python_source_rebinds_mounted_component(tmp_path, monkeypatch):
    from psx import App, Flex, Text, component
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    source = tmp_path / "main.py"
    source.write_text(
        "from psx import Flex, Text\n"
        "class ExternalExample:\n"
        "    def render(self):\n"
        "        return Flex(Text('updated from file'))\n",
        encoding="utf-8",
    )
    context = ExternalExample()
    holder = [lambda self: Flex(Text("previous view"))]
    def root():
        return holder[0](context)
    definition = component(root)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )
    context.app = App(definition, renderer=renderer)
    context._development_root_definition = definition
    context._development_render = holder
    context.app.mount()
    original = context.app.reconciler.root.native_handle()
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *a: (frozenset(), {}))
    try:
        assert refresh.refresh_context_source(context, source, ("main.py",))
        assert context.app.reconciler.root.native_handle() is original
        assert original.children[0].props["value"] == "updated from file"
    finally:
        context.app.unmount()


def test_invalid_changed_module_is_rejected_before_reload(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("class Example: pass", encoding="utf-8")
    dependency = tmp_path / "helper.py"
    dependency.write_text("def broken(:\n", encoding="utf-8")
    context, _, original = make_context(entry)
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(
        refresh, "_project_modules",
        lambda *_: (frozenset({"helper"}), {"helper": dependency}),
    )
    reloaded = []
    monkeypatch.setattr(refresh, "_reload_module", reloaded.append)
    with pytest.raises(SyntaxError):
        refresh.refresh_context_source(context, entry, ("helper.py",))
    assert reloaded == []
    assert context._development_render[0] is original


def test_new_installed_third_party_import_can_load_in_process(tmp_path):
    from psx.devtools.qyro_reload import _load_updated_class

    authored = tmp_path / "main.py"
    authored.write_text(
        "import pandas as pd\n"
        "class ExternalExample:\n"
        "    def render(self):\n"
        "        return pd.__version__\n",
        encoding="utf-8",
    )
    refreshed = _load_updated_class(authored, ExternalExample, frozenset())
    import pandas
    assert refreshed.render(ExternalExample()) == pandas.__version__


def test_stylesheet_edit_recomputes_css_without_remounting_headless_component(
    tmp_path, monkeypatch
):
    from psx import App, component
    from psx.css.context import scoped_css_resources
    from psx.css.visual_values import CssColor
    from psx.markup.compile import psx
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    source = tmp_path / "main.py"
    source.write_text("class Example: pass", encoding="utf-8")
    css = tmp_path / "theme.css"
    css.write_text(".panel {color: #fff}", encoding="utf-8")
    context = SimpleNamespace()
    def render_view(self):
        with scoped_css_resources(["theme.css"], resolver=lambda _: css.read_text()):
            return psx('<div class="panel">Hello</div>')
    holder = [render_view]
    def root():
        return holder[0](context)
    definition = component(root)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )
    context.app = App(definition, renderer=renderer)
    context._development_root_definition = definition
    context._development_render = holder
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    try:
        context.app.mount()
        original = context.app.reconciler.root.native_handle()
        first = context.app.reconciler.root.children[0].node.css_computed
        assert first.properties["color"] == CssColor("#fff")
        css.write_text(".panel {color: #000}", encoding="utf-8")
        assert refresh.refresh_context_source(context, source, ("theme.css",))
        assert context.app.reconciler.root.native_handle() is original
        last = context.app.reconciler.root.children[0].node.css_computed
        assert last.properties["color"] == CssColor("#000")
    finally:
        context.app.unmount()


def test_local_from_import_rebinds_after_dependency_edit(tmp_path, monkeypatch):
    import importlib
    import sys
    from psx import App, Flex, Text, component
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    monkeypatch.syspath_prepend(str(tmp_path))
    helper = tmp_path / "refresh_helper.py"
    helper.write_text("def label():\n    return 'before module edit'\n", encoding="utf-8")
    source = tmp_path / "main.py"
    source.write_text(
        "from refresh_helper import label\n"
        "from psx import Flex, Text\n"
        "class ExternalExample:\n"
        "    def render(self):\n"
        "        return Flex(Text(label()))\n",
        encoding="utf-8",
    )
    context = ExternalExample()
    holder = [lambda self: Flex(Text("before module edit"))]
    def root():
        return holder[0](context)
    definition = component(root)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )
    context.app = App(definition, renderer=renderer)
    context._development_root_definition = definition
    context._development_render = holder
    importlib.import_module("refresh_helper")
    try:
        context.app.mount()
        host = context.app.reconciler.root.native_handle()
        helper.write_text("def label():\n    return 'after module edit'\n", encoding="utf-8")
        assert refresh.refresh_context_source(context, source, ("refresh_helper.py",))
        assert context.app.reconciler.root.native_handle() is host
        assert host.children[0].props["value"] == "after module edit"
    finally:
        context.app.unmount()
        sys.modules.pop("refresh_helper", None)


def test_invalid_edit_resets_stale_previous_remount_status(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    entry.write_text("def broken(:\n", encoding="utf-8")
    context, reconciler, original = make_context(entry)
    reconciler._coordinated_remount_applied = True
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    with pytest.raises(SyntaxError):
        refresh.refresh_context_source(context, entry, ("main.py",))
    assert reconciler._coordinated_remount_applied is False
    assert context._development_render[0] is original


def test_rejected_syntax_edit_can_be_corrected_without_restarting(tmp_path, monkeypatch):
    entry = tmp_path / "main.py"
    context, reconciler, old_render = make_context(entry)
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    replacement = lambda self: "recovered"
    monkeypatch.setattr(
        refresh, "_load_updated_class",
        lambda *_: SimpleNamespace(render=replacement),
    )
    entry.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(SyntaxError):
        refresh.refresh_context_source(context, entry, ("main.py",))
    assert context._development_render[0] is old_render
    assert reconciler.calls == []
    entry.write_text("class Example: pass\n", encoding="utf-8")
    assert refresh.refresh_context_source(context, entry, ("main.py",))
    assert context._development_render[0] is replacement
    assert reconciler.calls == [reconciler.root]


def test_root_host_switch_requests_restart_before_native_teardown():
    from psx import Flex, Text, component, psx
    from psx.core.errors import RootHostTransitionRequiresRestart
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    current = [psx("<div><p>Before</p></div>")]

    @component
    def root():
        return current[0]

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(480, True), AvailableSize(320, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(12, 80, 18, 18, 80, 18),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(root())
        original = mounted.native_handle()
        current[0] = Flex(Text("After"), direction="column")
        reconciler._coordinated_remount = True
        with pytest.raises(RootHostTransitionRequiresRestart):
            reconciler.try_reevaluate(mounted)
        assert mounted.native_handle() is original
        assert not mounted.children[0].disposed
    finally:
        reconciler._coordinated_remount = False
        reconciler.unmount()


def test_fast_refresh_swaps_div_and_flex_hosts_without_disposing_component():
    from psx import Flex, Text, component, psx, use_state
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    use_flex = [False]

    @component
    def root():
        count, _ = use_state(7)
        if use_flex[0]:
            return Flex(Text(str(count)), direction="column")
        return psx("<div><p>Count</p></div>")

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(360, True), AvailableSize(240, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(24, 80, 18, 18, 80, 18),
    )
    reconciler = Reconciler(renderer)
    try:
        boundary = reconciler.render(root())
        first = boundary.native_handle()
        reconciler._coordinated_remount = True
        use_flex[0] = True
        assert reconciler.try_reevaluate(boundary)
        assert reconciler.root is boundary
        assert not boundary.disposed
        assert boundary.native_handle() is not first
        assert boundary.native_handle().node_type == "Flex"
        assert boundary.native_handle().children[0].props["value"] == "7"
        use_flex[0] = False
        assert reconciler.try_reevaluate(boundary)
        assert reconciler.root is boundary
        assert boundary.native_handle().node_type == "div"
    finally:
        reconciler._coordinated_remount = False
        reconciler.unmount()


def test_root_fragment_mounts_multiple_siblings_and_updates_state_without_native_wrapper_in_markup():
    from psx import component, psx, use_state
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    from psx.core.vnode import NodeKind

    set_count = []
    @component
    def Root():
        count, set_value = use_state(0)
        set_count.append(set_value)
        return psx(f"<><h1>Hello World!</h1><p>Count: {count}</p><button>Increment</button></>")

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(360, True),
                                           AvailableSize(240, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(65, 65, 20, 20, 65, 20),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(Root())
        assert mounted.node.kind is NodeKind.COMPONENT
        assert mounted.children[0].node.type == "div"
        assert [child.node.type for child in mounted.children[0].children] == [
            "h1", "p", "Button",
        ]
        previous = mounted.children[0].native_handle()
        set_count[-1](lambda count: count + 1)
        renderer.flush()
        assert reconciler.root is mounted
        assert mounted.children[0].native_handle() is previous
        assert mounted.children[0].children[1].children[0].handle.props["value"] == "Count: 1"
    finally:
        reconciler.unmount()


def test_direct_fragment_is_accepted_as_layout_root():
    from psx import psx
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(360, True),
                                           AvailableSize(240, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(75, 75, 22, 22, 75, 22),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("<><h1>Title</h1><p>Body</p></>"))
        assert mounted.node.type == "div"
        assert len(mounted.children) == 2
        assert renderer.sfle_result is not None
    finally:
        reconciler.unmount()


def test_hot_refresh_loads_new_top_level_decorated_component_without_restart(tmp_path):
    from psx.devtools.qyro_reload import _load_updated_class
    from psx.core.vnode import NodeKind

    source = tmp_path / "main.py"
    source.write_text(
        "from psx import component, psx\\n"
        "class ExternalExample:\\n"
        "    def render(self):\\n"
        "        return psx('<div><p>Initial</p></div>')\\n",
        encoding="utf-8",
    )
    source.write_text(
        "from psx import component, psx\\n"
        "@component\\n"
        "def SecondaryComponent():\\n"
        "    return psx('<p>Secondary Component</p>')\\n"
        "class ExternalExample:\\n"
        "    def render(self):\\n"
        "        return psx('<div><SecondaryComponent /></div>')\\n",
        encoding="utf-8",
    )
    candidate = _load_updated_class(source, ExternalExample, frozenset())
    view = candidate.render(ExternalExample())
    assert view.type == "div"
    assert view.children[0].kind is NodeKind.COMPONENT
    assert view.children[0].type.__name__ == "SecondaryComponent"


def test_refresh_candidate_omits_unrelated_bootstrap_but_keeps_components():
    from psx.devtools.qyro_reload import _render_class_source
    source = (
        "from psx import component, psx\\n"
        "@component\\n"
        "def SecondaryComponent():\\n"
        "    return psx('<p>ok</p>')\\n"
        "raise RuntimeError('must not execute startup')\\n"
        "class ExternalExample:\\n"
        "    def render(self):\\n"
        "        return psx('<SecondaryComponent />')\\n"
    )
    candidate = _render_class_source(source, "ExternalExample", frozenset())
    assert "def SecondaryComponent" in candidate
    assert "must not execute startup" not in candidate

