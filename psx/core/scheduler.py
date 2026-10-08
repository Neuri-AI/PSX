"""Per-root coalescing scheduler for component updates and post-commit effects."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .instance import MountedInstance


class Scheduler:
    """Batches state changes and crosses into the renderer's UI event loop once."""

    def __init__(
        self,
        schedule_ui: Callable[[Callable[[], None]], None],
        flush_dirty: Callable[[tuple[MountedInstance, ...]], None],
    ) -> None:
        self._schedule_ui = schedule_ui
        self._flush_dirty = flush_dirty
        self._lock = threading.RLock()
        self._dirty: dict[int, MountedInstance] = {}
        self._effects: dict[tuple[int, int], Callable[[], None]] = {}
        self._pending = False

    def mark_dirty(self, instance: MountedInstance) -> None:
        """Queue a component boundary; this method is safe to call from a worker."""
        with self._lock:
            if instance.disposed:
                return
            self._dirty[id(instance)] = instance
            if self._pending:
                return
            self._pending = True
        self._schedule_ui(self._flush)

    def queue_effect(self, instance: MountedInstance, index: int, runner: Callable[[], None]) -> None:
        with self._lock:
            self._effects[(id(instance), index)] = runner

    def run_effects(self) -> None:
        """Run effects after a successful commit; effects may schedule a later flush."""
        with self._lock:
            queued = tuple(self._effects.values())
            self._effects.clear()
        for runner in queued:
            runner()

    def _flush(self) -> None:
        with self._lock:
            dirty = tuple(self._dirty.values())
            self._dirty.clear()
            self._pending = False
        if dirty:
            self._flush_dirty(dirty)
