"""Supervised child-process restart for PSX development sessions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

from .classifier import ChangeKind, classify_change
from .config import HotReloadConfig
from .watcher import PollingFileWatcher


@dataclass(frozen=True, slots=True)
class ReloadDiagnostic:
    action: str
    message: str
    path: Path | None = None


class DevelopmentSupervisor:
    """Keep a development child process running and restart it on safe triggers.

    The supervisor never imports the application's modules. This is the
    reliable M8 baseline for native toolkits, closures and module globals.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        root: Path,
        config: HotReloadConfig,
        environment: dict[str, str] | None = None,
        diagnostics: Callable[[ReloadDiagnostic], None] | None = None,
    ) -> None:
        if not command:
            raise ValueError("A development supervisor requires a child command.")
        self.command = tuple(command)
        self.root = root.resolve()
        self.config = config
        self.environment = environment
        self.diagnostics = diagnostics or _print_diagnostic
        self._child: subprocess.Popen[bytes] | None = None
        self._watcher: PollingFileWatcher | None = None
        self._prepared_entry: tempfile.TemporaryDirectory[str] | None = None
        self._lock = threading.RLock()
        self._stopped = False

    @property
    def child_pid(self) -> int | None:
        return self._child.pid if self._child is not None and self._child.poll() is None else None

    def start(self) -> None:
        if not self.config.effective_enabled:
            self.diagnostics(ReloadDiagnostic("DISABLED", "Hot reload is disabled outside an explicit development session."))
            self._start_child()
            return
        self._start_child()
        self._watcher = PollingFileWatcher(
            self.root,
            self._on_changes,
            debounce_seconds=self.config.debounce_seconds,
            poll_interval_seconds=self.config.poll_interval_seconds,
        )
        self._watcher.start()
        self.diagnostics(ReloadDiagnostic("WATCHING", f"Watching {self.root}"))

    def run(self) -> int:
        """Start and wait for the child; stop cleanly on Ctrl-C."""
        self.start()
        try:
            child = self._child
            return child.wait() if child is not None else 1
        except KeyboardInterrupt:
            return 130
        finally:
            self.stop()

    def stop(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            if self._watcher is not None:
                self._watcher.stop()
                self._watcher = None
            self._stop_child()
            self._cleanup_prepared_entry()

    def restart(self, reason: str, path: Path | None = None) -> None:
        with self._lock:
            if self._stopped:
                return
            self.diagnostics(ReloadDiagnostic("PROCESS_RESTART", reason, path))
            self._stop_child()
            self._start_child()

    def _on_changes(self, paths: tuple[Path, ...]) -> None:
        plans = [classify_change(path, root=self.root) for path in paths]
        restart = next((plan for plan in plans if plan.kind is ChangeKind.PROCESS_RESTART), None)
        if restart is not None:
            self.restart(restart.reason, restart.path)

    def _start_child(self) -> None:
        environment = dict(os.environ)
        if self.environment:
            environment.update(self.environment)
        environment["PSX_HOT_RELOAD_CHILD"] = "1"
        existing_path = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(self.root) + (os.pathsep + existing_path if existing_path else "")
        kwargs: dict[str, object] = {"cwd": self.root, "env": environment}
        if os.name == "posix":
            kwargs["start_new_session"] = True
        self._child = subprocess.Popen(self._prepared_command(), **kwargs)  # type: ignore[arg-type]
        self.diagnostics(ReloadDiagnostic("STARTED", f"Started child process {self._child.pid}"))

    def _stop_child(self) -> None:
        child = self._child
        if child is None or child.poll() is not None:
            return
        if os.name == "posix":
            os.killpg(child.pid, signal.SIGTERM)
        else:
            child.terminate()
        try:
            child.wait(timeout=self.config.restart_grace_seconds)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.kill()
            child.wait()
        self.diagnostics(ReloadDiagnostic("STOPPED", f"Stopped child process {child.pid}"))

    def _prepared_command(self) -> tuple[str, ...]:
        """Statically prepare literal M4B markup before starting a child."""
        self._cleanup_prepared_entry()
        entry = Path(self.command[-1])
        if entry.suffix != ".py" or not entry.is_file():
            return self.command
        source = entry.read_text(encoding="utf-8")
        if "psx(" not in source:
            return self.command
        from psx.markup.transform import transform_source

        transformed = transform_source(source, filename=str(entry))
        if transformed.transformed_calls == 0:
            return self.command
        self._prepared_entry = tempfile.TemporaryDirectory(prefix="psx-dev-")
        generated = Path(self._prepared_entry.name) / entry.name
        generated.write_text(transformed.source, encoding="utf-8")
        return (*self.command[:-1], str(generated))

    def _cleanup_prepared_entry(self) -> None:
        if self._prepared_entry is not None:
            self._prepared_entry.cleanup()
            self._prepared_entry = None


def _print_diagnostic(diagnostic: ReloadDiagnostic) -> None:
    suffix = f": {diagnostic.path}" if diagnostic.path is not None else ""
    print(f"[PSX Dev] {diagnostic.action}: {diagnostic.message}{suffix}", file=sys.stderr, flush=True)
