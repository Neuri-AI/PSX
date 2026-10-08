"""Configuration and hard safety gates for PSX development tooling."""

from __future__ import annotations

from dataclasses import dataclass
import os
import sys
from pathlib import Path


def is_frozen_runtime() -> bool:
    """Return whether this process runs from a frozen application bundle."""
    if bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS"):
        return True
    try:
        from qyro import is_frozen
    except ImportError:
        return False
    return bool(is_frozen())


@dataclass(frozen=True, slots=True)
class HotReloadConfig:
    """Development supervisor configuration.

    Hot reload is intentionally opt-in. ``enabled`` is additionally gated by
    development mode and frozen-runtime detection, so a packaged application
    cannot accidentally start a watcher.
    """

    enabled: bool = True
    development: bool = True
    debounce_seconds: float = 0.25
    poll_interval_seconds: float = 0.10
    restart_grace_seconds: float = 3.0
    max_snapshot_bytes: int = 65_536
    root: Path | None = None

    @property
    def effective_enabled(self) -> bool:
        return self.enabled and self.development and not is_frozen_runtime()

    @classmethod
    def from_environment(cls, *, root: Path | None = None) -> "HotReloadConfig":
        """Read explicit opt-in flags without changing production defaults."""
        truthy = {"1", "true", "yes", "on"}
        falsy = {"0", "false", "no", "off"}
        requested = os.environ.get("PSX_HOT_RELOAD", "")
        development = os.environ.get("PSX_ENV", "").lower()
        return cls(
            enabled=False if requested.lower() in falsy else True,
            development=development not in {"production", "prod"},
            root=root,
        )
