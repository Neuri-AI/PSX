"""Apply CLI-delivered source edits to a mounted Velto root on its UI thread.

This module never watches the filesystem or owns a child process.
"""
from __future__ import annotations

import ast
from pathlib import Path
import os

from psx.core.vnode import NodeKind

from .qyro_reload import (
    _load_updated_class,
    _project_modules,
    _reload_module,
    _reload_policy,
)


def _mounted_root(instance, definition):
    if instance is None:
        return None
    if instance.node.kind is NodeKind.COMPONENT and instance.node.type is definition:
        return instance
    for child in instance.children:
        matching = _mounted_root(child, definition)
        if matching is not None:
            return matching
    return None


def refresh_context_source(context, source: Path, paths: tuple[str, ...]) -> bool:
    """Reevaluate compatible source edits while keeping root and hooks intact.

    Called ONLY from the renderer UI scheduler. Failures restore the previous
    compiled render callable; incompatible hook changes are deferred to the
    dedicated remount stage rather than forcing an unsafe partial update.
    """
    source = source.resolve()
    project = Path(os.environ.get('VELTO_PROJECT_ROOT', os.getcwd())).resolve()
    root = project if source.is_relative_to(project) else source.parent
    changed = set()
    for relative in paths:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Changed file is outside the project root") from exc
        changed.add(candidate)
    if not changed:
        return False

    app = getattr(context, "app", None)
    definition = getattr(context, "_development_root_definition", None)
    compiled = getattr(context, "_development_render", None)
    if app is None or definition is None or not isinstance(compiled, list) or len(compiled) != 1:
        return False
    instance = _mounted_root(app.reconciler.root, definition)
    if instance is None:
        return False

    policy = _reload_policy(context)
    _, module_paths = _project_modules(source, root, policy)
    modules_changed = {name for name, path in module_paths.items() if path in changed}
    css_changed = any(path.suffix.lower() == ".css" for path in changed)
    if source not in changed and not modules_changed and not css_changed:
        return False

    for path in sorted(changed):
        if path.suffix == ".py" and (path == source or path in module_paths.values()):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    previous = compiled[0]
    try:
        # Import only project-owned source modules; do not reload native or
        # third-party extensions already running in the interpreter.
        for name in sorted(modules_changed):
            _reload_module(name)
        if source in changed or modules_changed:
            candidate = _load_updated_class(source, type(context), frozenset(module_paths))
            compiled[0] = candidate.render
        reconciler = app.reconciler
        previously_enabled = getattr(reconciler, '_coordinated_remount', False)
        reconciler._coordinated_remount = True
        try:
            compatible = reconciler.try_reevaluate(instance)
        finally:
            reconciler._coordinated_remount = previously_enabled
        if compatible:
            # A targeted reevaluation must finish the same layout/ref/effect
            # commit that a normal reconciler render performs.
            renderer = app.reconciler.renderer
            commit_layout = getattr(renderer, 'commit_layout', None)
            if callable(commit_layout):
                commit_layout(app.reconciler.root)
            commit_refs = getattr(app.reconciler, '_commit_refs', None)
            if callable(commit_refs):
                commit_refs()
            app.reconciler.scheduler.run_effects()
            return True
        remount = getattr(app.reconciler, 'remount_component', None)
        if callable(remount):
            remount(instance)
            return True
        compiled[0] = previous
        return False
    except Exception:
        # Cleanup can raise after the replacement is mounted. Never restore
        # an obsolete render callable onto an already replaced boundary.
        if not instance.disposed:
            compiled[0] = previous
        raise
