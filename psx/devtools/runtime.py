"""Compatible in-process component refresh using the existing reconciler."""

from __future__ import annotations

import importlib
from types import ModuleType

from psx.core.instance import MountedInstance
from psx.core.reconcile import Reconciler
from psx.core.vnode import NodeKind


class ComponentRefreshManager:
    """Reload a project-owned module and refresh its mounted components.

    This intentionally supports normal importable modules only. Entry-point
    bootstrap code, native state, non-importable scripts and hook-incompatible
    changes must use the development supervisor's restart fallback.
    """

    def __init__(self, reconciler: Reconciler) -> None:
        self.reconciler = reconciler

    def refresh_module(self, module: ModuleType) -> int:
        """Reload ``module`` and queue its compatible mounted boundaries.

        Returns the number of boundaries scheduled. ``HookOrderError`` remains
        a deliberate compatibility signal for callers that choose a restart.
        """
        module_name = module.__name__
        importlib.invalidate_caches()
        importlib.reload(module)
        root = self.reconciler.root
        if root is None:
            return 0
        targets = tuple(_matching_components(root, module_name))
        for instance in targets:
            self.reconciler.scheduler.mark_dirty(instance)
        return len(targets)


def _matching_components(instance: MountedInstance, module_name: str):
    if instance.node.kind is NodeKind.COMPONENT:
        render = getattr(instance.node.type, "render", None)
        if getattr(render, "__module__", None) == module_name:
            yield instance
    for child in instance.children:
        yield from _matching_components(child, module_name)
