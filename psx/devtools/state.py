"""Explicit, JSON-only snapshots for supervised restarts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json


SnapshotGetter = Callable[[], object]
SnapshotRestorer = Callable[[object], None]


@dataclass(frozen=True, slots=True)
class StateRegistration:
    name: str
    version: int
    get: SnapshotGetter
    restore: SnapshotRestorer


class StateSnapshotRegistry:
    """Opt-in registry that rejects non-JSON state and oversized snapshots."""

    def __init__(self, *, max_bytes: int = 65_536) -> None:
        self._max_bytes = max_bytes
        self._entries: dict[str, StateRegistration] = {}

    def register(
        self, name: str, get: SnapshotGetter, restore: SnapshotRestorer, *, version: int = 1
    ) -> None:
        if not name or name in self._entries:
            raise ValueError("State registration names must be unique and non-empty.")
        self._entries[name] = StateRegistration(name, version, get, restore)

    def snapshot(self) -> str:
        payload = {
            name: {"version": item.version, "value": item.get()}
            for name, item in self._entries.items()
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if len(encoded.encode("utf-8")) > self._max_bytes:
            raise ValueError("PSX development state snapshot exceeds the configured size limit.")
        return encoded

    def restore(self, encoded: str) -> tuple[str, ...]:
        """Restore matching versioned entries; return skipped entry names."""
        raw = json.loads(encoded)
        if not isinstance(raw, dict):
            raise ValueError("PSX development state snapshot must be a JSON object.")
        skipped: list[str] = []
        for name, data in raw.items():
            entry = self._entries.get(name)
            if entry is None or not isinstance(data, dict) or data.get("version") != entry.version:
                skipped.append(str(name))
                continue
            entry.restore(data.get("value"))
        return tuple(skipped)
