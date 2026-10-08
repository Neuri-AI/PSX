"""Automatic compatible refresh for a mounted Qyro PSX component."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import fnmatch
import importlib
import importlib.util
import inspect
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable

from psx.core.instance import MountedInstance
from psx.core.vnode import NodeKind
from psx.markup.transform import transform_source

from .config import HotReloadConfig
from .watcher import PollingFileWatcher


@dataclass(frozen=True, slots=True)
class ModuleReloadPolicy:
    enabled: bool = True
    watch: tuple[str, ...] = (".",)
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    third_party: str = "restart"
    preserve_state: bool = True
    fallback: str = "restart"


class QyroComponentReloader:
    """Watch one Qyro-authored component source file in a development process.

    The existing native host and PSX root are retained. A successful source
    update replaces only the class render method, then enters the normal PSX
    scheduler/reconciler path. Invalid source leaves the last good UI mounted.
    """

    def __init__(self, host: object, *, report: Callable[[str], None] | None = None) -> None:
        self.host = host
        self.report = report or _report
        self.source = _source_path(host)
        self.root = self.source.parent
        self.policy = _reload_policy(host)
        self.modules, self.module_paths = _project_modules(self.source, self.root, self.policy)
        self._watcher: PollingFileWatcher | None = None

    def start(self) -> bool:
        config = HotReloadConfig.from_environment(root=self.source.parent)
        if not config.effective_enabled or not self.policy.enabled:
            self.report("DISABLED: frozen runtime or production configuration")
            return False
        self._watcher = PollingFileWatcher(
            self.source.parent,
            self._on_changes,
            debounce_seconds=config.debounce_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        self._watcher.start()
        self.report(f"WATCHING: {self.source}")
        return True

    def stop(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def _on_changes(self, paths: tuple[Path, ...]) -> None:
        paths = tuple(path for path in paths if self._is_watched(path))
        if not paths:
            return
        affected_modules = tuple(
            name for name, module_path in self.module_paths.items() if module_path in paths
        )
        if self.source not in paths and not affected_modules:
            return
        try:
            # The entry may have gained a new local import since the last
            # save, so rebuild the project dependency view before loading the
            # candidate class.
            self.policy = _reload_policy(self.host)
            self.modules, self.module_paths = _project_modules(self.source, self.root, self.policy)
            affected_modules = tuple(
                name for name, module_path in self.module_paths.items() if module_path in paths
            )
            for name in affected_modules:
                _reload_module(name)
            updated = _load_updated_class(self.source, type(self.host), self.modules)
            setattr(type(self.host), "render", getattr(updated, "render"))
            mounted = getattr(self.host, "_psx_mount", None)
            root_component = getattr(self.host, "_psx_root_component", None)
            if mounted is None or root_component is None:
                raise RuntimeError("PSX root is not mounted.")
            instance = _find_component(mounted.app.reconciler.root, root_component)
            if instance is None:
                raise RuntimeError("Mounted Qyro PSX component boundary was not found.")
            mounted.app.reconciler.scheduler.mark_dirty(instance)
            self.report("HOT_UPDATE: render method replaced")
        except Exception as exc:
            # Keep the last successful tree alive; the next save retries.
            self.report(f"FAILED: {exc}")

    def _is_watched(self, path: Path) -> bool:
        if path == self.source:
            return True
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            return False
        return any(
            pattern in {".", "./"}
            or relative.startswith(pattern.rstrip("/") + "/")
            or fnmatch.fnmatch(relative, pattern)
            for pattern in self.policy.watch
        )


def _source_path(host: object) -> Path:
    configured = os.environ.get("PSX_SOURCE_ENTRY")
    candidate = Path(configured) if configured else Path(inspect.getsourcefile(type(host)) or "")
    if not candidate.is_file():
        raise RuntimeError("Cannot determine a PSX Qyro component source file for hot reload.")
    return candidate.resolve()


def _load_updated_class(source: Path, previous: type[object], modules: frozenset[str]) -> type[object]:
    text = source.read_text(encoding="utf-8")
    transformed = transform_source(text, filename=str(source))
    candidate_source = _render_class_source(
        transformed.source if transformed.transformed_calls else text,
        previous.__name__,
        modules,
    )
    with tempfile.TemporaryDirectory(prefix="psx-qyro-reload-") as directory:
        generated = Path(directory) / source.name
        generated.write_text(candidate_source, encoding="utf-8")
        module_name = f"_psx_qyro_reload_{id(previous)}"
        spec = importlib.util.spec_from_file_location(module_name, generated)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load updated PSX source.")
        module = importlib.util.module_from_spec(spec)
        # Preserve the original module's long-lived globals (notably existing
        # Pydux stores) and execute only the updated class/factory declarations.
        module.__dict__.update(
            {
                name: value
                for name, value in getattr(previous.render, "__globals__", {}).items()
                if name not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__cached__"}
            }
        )
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            target: object = module
            for part in previous.__qualname__.split("."):
                if part == "<locals>":
                    raise RuntimeError("Nested Qyro component classes require a process restart.")
                target = getattr(target, part)
            if not isinstance(target, type):
                raise RuntimeError("Updated Qyro component class was not found.")
            _stop_candidate_inspectors(module)
            return target
        finally:
            sys.modules.pop(module_name, None)


def _render_class_source(source: str, class_name: str, modules: frozenset[str]) -> str:
    """Keep reload candidates free of application bootstrap side effects."""
    tree = ast.parse(source)
    selected: list[ast.stmt] = []
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef) and statement.name == class_name:
            selected.append(statement)
        elif isinstance(statement, ast.ImportFrom):
            # An added import must be rebound in the candidate namespace. This
            # imports a newly referenced dependency once; it never reloads a
            # third-party module, whose source remains outside the project
            # dependency graph and therefore follows the restart policy.
            selected.append(statement)
        elif isinstance(statement, ast.Import):
            selected.append(statement)
        elif isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id.startswith("_psx_template_")
            for target in statement.targets
        ):
            selected.append(statement)
    if not any(isinstance(statement, ast.ClassDef) and statement.name == class_name for statement in selected):
        raise RuntimeError(f"Updated class {class_name!r} was not found.")
    tree.body = selected
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _stop_candidate_inspectors(module: object) -> None:
    """Avoid retaining a Pydux inspector created while loading a candidate.

    The currently mounted component continues using its existing store. The
    candidate module is loaded solely to obtain its updated render method.
    Arbitrary import-time side effects remain an incompatibility that should
    use a process restart rather than be treated as a universal hot update.
    """
    for value in vars(module).values():
        inspector = getattr(value, "inspector", None)
        stop = getattr(inspector, "stop", None)
        if callable(stop):
            stop()


def _reload_policy(host: object) -> ModuleReloadPolicy:
    """Read the optional, project-scoped hot-reload policy from Qyro settings."""
    try:
        settings = host.container.load_settings_use_case.execute().raw_settings
        raw = settings.get("hot_reload", {})
    except Exception:
        return ModuleReloadPolicy()
    if not isinstance(raw, dict):
        return ModuleReloadPolicy()
    module = raw.get("module_reload", {})
    if not isinstance(module, dict):
        module = {}
    def strings(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value) if isinstance(value, list) and all(isinstance(item, str) for item in value) else default
    return ModuleReloadPolicy(
        enabled=raw.get("enabled", True) is not False,
        watch=strings(raw.get("watch"), (".",)),
        include=strings(module.get("include"), ()),
        exclude=strings(module.get("exclude"), ()),
        third_party=module.get("third_party", "restart") if isinstance(module.get("third_party", "restart"), str) else "restart",
        preserve_state=raw.get("preserve_state", True) is not False,
        fallback=raw.get("fallback", "restart") if isinstance(raw.get("fallback", "restart"), str) else "restart",
    )


def _project_modules(
    source: Path, root: Path, policy: ModuleReloadPolicy
) -> tuple[frozenset[str], dict[str, Path]]:
    """Build a local import graph without treating third-party imports as safe.

    Any ``.py`` module reachable from the entry under the project root is a
    project-owned reload candidate. This includes newly created modules and
    nested packages; settings can add modules not reachable by static imports.
    """
    discovered: dict[str, Path] = {}
    pending = list(_imports_in(source)) + _expand_includes(root, policy.include)
    while pending:
        name = pending.pop()
        if _matches_any(name, policy.exclude):
            continue
        if name in discovered:
            continue
        path = _local_module_path(name, root)
        if path is None:
            continue
        discovered[name] = path
        pending.extend(_imports_in(path))
    return frozenset(discovered), discovered


def _expand_includes(root: Path, patterns: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        parts = relative.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        name = ".".join(parts)
        if _matches_any(name, patterns):
            names.append(name)
    return names


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _imports_in(source: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, SyntaxError):
        return ()
    names: list[str] = []
    for statement in ast.walk(tree):
        if isinstance(statement, ast.Import):
            names.extend(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.level == 0 and statement.module:
            names.append(statement.module)
    return tuple(names)


def _local_module_path(name: str, root: Path) -> Path | None:
    candidate = root.joinpath(*name.split("."))
    source = candidate.with_suffix(".py")
    package = candidate / "__init__.py"
    for path in (source, package):
        if path.is_file():
            return path.resolve()
    return None


def _reload_module(name: str) -> None:
    importlib.invalidate_caches()
    module = sys.modules.get(name)
    if module is None:
        importlib.import_module(name)
    else:
        importlib.reload(module)


def _find_component(instance: MountedInstance | None, definition: object) -> MountedInstance | None:
    if instance is None:
        return None
    if instance.node.kind is NodeKind.COMPONENT and instance.node.type is definition:
        return instance
    for child in instance.children:
        found = _find_component(child, definition)
        if found is not None:
            return found
    return None


def _report(message: str) -> None:
    print(f"[PSX Dev] {message}", file=sys.stderr, flush=True)
