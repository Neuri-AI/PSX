"""Conservative change classification for the development supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ChangeKind(str, Enum):
    """The action selected for a changed path."""

    PROCESS_RESTART = "PROCESS_RESTART"
    IGNORED = "IGNORED"


@dataclass(frozen=True, slots=True)
class ChangePlan:
    kind: ChangeKind
    reason: str
    path: Path


_RESTART_FILES = frozenset({"pyproject.toml", "poetry.lock", "requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg"})
_NATIVE_SUFFIXES = frozenset({".so", ".pyd", ".dylib", ".dll"})
_IGNORED_PARTS = frozenset({"__pycache__", ".git", ".hg", ".svn", ".venv", "venv", "build", "dist", ".mypy_cache", ".pytest_cache"})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo", "~", ".swp", ".tmp"})


def classify_change(path: Path, *, root: Path) -> ChangePlan:
    """Classify only project-owned source/configuration changes.

    M8 deliberately uses a supervised restart as the safe baseline.  It does
    not call ``importlib.reload`` behind the developer's back: mounted
    closures, ``from x import y`` bindings and native toolkit state cannot be
    proven safe from a changed pathname alone.
    """
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ChangePlan(ChangeKind.IGNORED, "outside project root", path)
    if any(part in _IGNORED_PARTS or part.startswith(".") and part not in {".env"} for part in relative.parts):
        return ChangePlan(ChangeKind.IGNORED, "generated or environment path", path)
    if path.name.startswith(".") or path.name.endswith(tuple(_IGNORED_SUFFIXES)):
        return ChangePlan(ChangeKind.IGNORED, "temporary editor artifact", path)
    if path.name in _RESTART_FILES:
        return ChangePlan(ChangeKind.PROCESS_RESTART, "dependency or build configuration changed", path)
    if path.suffix.lower() in _NATIVE_SUFFIXES:
        return ChangePlan(ChangeKind.PROCESS_RESTART, "native extension changed", path)
    if path.suffix.lower() == ".py":
        return ChangePlan(ChangeKind.PROCESS_RESTART, "project Python source changed", path)
    return ChangePlan(ChangeKind.IGNORED, "unsupported source type", path)
