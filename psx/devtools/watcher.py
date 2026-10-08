"""A small polling watcher used when no optional filesystem watcher is installed."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
import time

from .classifier import ChangeKind, classify_change


_Stamp = tuple[int, int]


class PollingFileWatcher:
    """Watch project files with debouncing and atomic-replace tolerance."""

    def __init__(
        self,
        root: Path,
        on_changes: Callable[[tuple[Path, ...]], None],
        *,
        debounce_seconds: float = 0.25,
        poll_interval_seconds: float = 0.10,
    ) -> None:
        self.root = root.resolve()
        self.on_changes = on_changes
        self.debounce_seconds = debounce_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._snapshot: dict[Path, _Stamp] = {}
        self._pending: set[Path] = set()
        self._last_change_at: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._snapshot = self._scan()
        self._thread = threading.Thread(target=self._run, name="psx-file-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval_seconds * 4))
            self._thread = None

    def poll_once(self, *, now: float | None = None) -> tuple[Path, ...]:
        """Perform one deterministic scan; useful for tests and custom loops."""
        now = time.monotonic() if now is None else now
        current = self._scan()
        changed = set(current).symmetric_difference(self._snapshot)
        changed.update(path for path in current.keys() & self._snapshot.keys() if current[path] != self._snapshot[path])
        self._snapshot = current
        for path in changed:
            if classify_change(path, root=self.root).kind is not ChangeKind.IGNORED:
                self._pending.add(path)
                self._last_change_at = now
        if self._pending and self._last_change_at is not None and now - self._last_change_at >= self.debounce_seconds:
            ready = tuple(sorted(self._pending))
            self._pending.clear()
            self._last_change_at = None
            self.on_changes(ready)
            return ready
        return ()

    def _run(self) -> None:
        while not self._stop.wait(self.poll_interval_seconds):
            self.poll_once()

    def _scan(self) -> dict[Path, _Stamp]:
        result: dict[Path, _Stamp] = {}
        if not self.root.is_dir():
            return result
        for path in self.root.rglob("*"):
            if not path.is_file() or classify_change(path, root=self.root).kind is ChangeKind.IGNORED:
                continue
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            result[path] = (stat.st_mtime_ns, stat.st_size)
        return result
