from __future__ import annotations

from pathlib import Path
import sys
import time
import importlib

import pytest

from psx.devtools import ChangeKind, DevelopmentSupervisor, HotReloadConfig, PollingFileWatcher, classify_change
from psx.devtools.state import StateSnapshotRegistry
from psx.devtools.runtime import ComponentRefreshManager
from psx.devtools.qyro_reload import ModuleReloadPolicy, _project_modules, _reload_policy, _render_class_source
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_classifier_restarts_project_python_and_ignores_caches(tmp_path: Path) -> None:
    source = tmp_path / "view.py"
    cache = tmp_path / "__pycache__" / "view.pyc"
    assert classify_change(source, root=tmp_path).kind is ChangeKind.PROCESS_RESTART
    assert classify_change(cache, root=tmp_path).kind is ChangeKind.IGNORED
    assert classify_change(tmp_path / "pyproject.toml", root=tmp_path).kind is ChangeKind.PROCESS_RESTART


def test_watcher_debounces_rapid_and_atomic_python_saves(tmp_path: Path) -> None:
    source = tmp_path / "view.py"
    source.write_text("value = 1\n", encoding="utf-8")
    observed: list[tuple[Path, ...]] = []
    watcher = PollingFileWatcher(tmp_path, observed.append, debounce_seconds=0.2)
    watcher._snapshot = watcher._scan()
    source.write_text("value = 2\n", encoding="utf-8")
    watcher.poll_once(now=1.0)
    replacement = tmp_path / "replacement.py"
    replacement.write_text("value = 3\n", encoding="utf-8")
    replacement.replace(source)
    watcher.poll_once(now=1.1)
    assert observed == []
    ready = watcher.poll_once(now=1.31)
    assert ready == (source,)
    assert observed == [(source,)]


def test_state_snapshots_are_explicit_json_and_versioned() -> None:
    state = {"count": 2}
    registry = StateSnapshotRegistry()
    registry.register("counter", lambda: state, lambda value: state.update(value))
    snapshot = registry.snapshot()
    state["count"] = 0
    assert registry.restore(snapshot) == ()
    assert state == {"count": 2}


def test_supervisor_restarts_child_without_overlap(tmp_path: Path) -> None:
    entry = tmp_path / "child.py"
    log = tmp_path / "starts.txt"
    entry.write_text(
        "from pathlib import Path\nimport time\n"
        f"Path({str(log)!r}).open('a').write('started\\n')\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    diagnostics = []
    config = HotReloadConfig(enabled=True, development=True, root=tmp_path, restart_grace_seconds=1)
    supervisor = DevelopmentSupervisor(
        [sys.executable, str(entry)], root=tmp_path, config=config, diagnostics=diagnostics.append
    )
    supervisor.start()
    try:
        first = supervisor.child_pid
        assert first is not None
        for _ in range(50):
            if log.exists():
                break
            time.sleep(0.02)
        supervisor.restart("project Python source changed", entry)
        second = supervisor.child_pid
        assert second is not None and second != first
        assert any(item.action == "PROCESS_RESTART" for item in diagnostics)
    finally:
        supervisor.stop()


def test_supervisor_prepares_literal_m4b_markup_for_its_child(tmp_path: Path) -> None:
    entry = tmp_path / "app.py"
    output = tmp_path / "result.txt"
    entry.write_text(
        "from pathlib import Path\nfrom psx import psx\n"
        "title = 'prepared'\n"
        "node = psx('<Text>{title}</Text>')\n"
        f"Path({str(output)!r}).write_text(str(node), encoding='utf-8')\n",
        encoding="utf-8",
    )
    supervisor = DevelopmentSupervisor(
        [sys.executable, str(entry)],
        root=tmp_path,
        config=HotReloadConfig(enabled=False, development=False, root=tmp_path),
        environment={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        diagnostics=lambda _: None,
    )
    supervisor.start()
    try:
        child = supervisor._child
        assert child is not None and child.wait(timeout=3) == 0
        assert "prepared" in output.read_text(encoding="utf-8")
    finally:
        supervisor.stop()


def test_production_configuration_does_not_enable_watcher() -> None:
    assert not HotReloadConfig(enabled=True, development=False).effective_enabled


def test_compatible_module_refresh_preserves_native_widget_identity(tmp_path: Path) -> None:
    module_name = "psx_hot_refresh_fixture"
    module_file = tmp_path / f"{module_name}.py"
    module_file.write_text(
        "from psx import Text, component\n"
        "@component\n"
        "def View():\n"
        "    return Text('one')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module(module_name)
        renderer = HeadlessRenderer()
        reconciler = Reconciler(renderer)
        root = reconciler.render(module.View())
        widget = root.children[0].handle
        module_file.write_text(
            "from psx import Text, component\n"
            "@component\n"
            "def View():\n"
            "    return Text('two updated')\n",
            encoding="utf-8",
        )
        assert ComponentRefreshManager(reconciler).refresh_module(module) == 1
        renderer.flush()
        assert root.children[0].handle is widget
        assert widget.props["value"] == "two updated"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(module_name, None)


def test_qyro_candidate_relinks_only_allowlisted_local_imports() -> None:
    source = """
from PySide6.QtWidgets import QMainWindow
from md import hi
import pandas as pd
from psx.markup import compile_template as _psx_compile_template
_psx_template_0 = _psx_compile_template('<Text>{value}</Text>')
class Window(QMainWindow):
    def render(self):
        hi()
        return _psx_template_0
"""
    candidate = _render_class_source(source, "Window", frozenset({"md"}))
    assert "from md import hi" in candidate
    assert "from PySide6.QtWidgets import QMainWindow" in candidate
    assert "import pandas as pd" in candidate
    assert "class Window" in candidate


def test_qyro_reload_discovers_nested_project_modules_without_settings(tmp_path: Path) -> None:
    (tmp_path / "features").mkdir()
    (tmp_path / "services").mkdir()
    entry = tmp_path / "main.py"
    view = tmp_path / "features" / "view.py"
    api = tmp_path / "services" / "api.py"
    entry.write_text("from features.view import View\n", encoding="utf-8")
    view.write_text("from services.api import title\n", encoding="utf-8")
    api.write_text("title = 'PSX'\n", encoding="utf-8")
    names, paths = _project_modules(entry, tmp_path, ModuleReloadPolicy())
    assert names == frozenset({"features.view", "services.api"})
    assert paths["services.api"] == api.resolve()


def test_qyro_settings_false_is_an_authoritative_hot_reload_opt_out() -> None:
    class Settings:
        raw_settings = {"hot_reload": {"enabled": False}}

    class Loader:
        def execute(self):
            return Settings()

    class Container:
        load_settings_use_case = Loader()

    class Host:
        container = Container()

    assert not _reload_policy(Host()).enabled


def test_qyro_settings_default_to_enabled_when_key_is_absent() -> None:
    class Settings:
        raw_settings = {"hot_reload": {}}

    class Loader:
        def execute(self):
            return Settings()

    class Container:
        load_settings_use_case = Loader()

    class Host:
        container = Container()

    assert _reload_policy(Host()).enabled
