"""Native SFLE-C5 explicit measurement invalidation state and generation fences.

Invalidations carry semantic reasons, coalesce duplicate notifications and
cannot be certified by the existence of an oracle alone. Backends schedule
their own UI-thread commits against the current mounted instance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

InvalidationReason = Literal[
    "content", "font", "theme", "resource", "dpi", "viewport",
]
REASONS = frozenset(("content", "font", "theme", "resource", "dpi", "viewport"))


@dataclass(slots=True)
class MeasurementInvalidations:
    epoch: int = 0
    committed_epoch: int = 0
    pending: set[str] = field(default_factory=set)
    dirty_widgets: set[int] = field(default_factory=set)
    invalidate_all: bool = False

    def request(self, reason: str, *, widget_id: int | None = None) -> int:
        if reason not in REASONS:
            raise ValueError(f"Unsupported SFLE measurement invalidation: {reason!r}")
        if widget_id is not None and (type(widget_id) is not int or widget_id <= 0):
            raise ValueError("Widget invalidation identity must be a positive integer.")
        # Repeated identical notices must not repeatedly stale an otherwise
        # current geometry commit. New reasons, target identities, and scope
        # escalation to global invalidation still advance the generation.
        changed = reason not in self.pending
        self.pending.add(reason)
        if widget_id is None:
            changed |= not self.invalidate_all
            self.invalidate_all = True
        elif not self.invalidate_all:
            changed |= widget_id not in self.dirty_widgets
            self.dirty_widgets.add(widget_id)
        if changed:
            self.epoch += 1
        return self.epoch

    def needs_commit(self) -> bool:
        return bool(self.pending)

    def is_current(self, epoch: int) -> bool:
        return epoch == self.epoch

    def acknowledge(self, epoch: int) -> bool:
        if not self.is_current(epoch):
            return False
        self.pending.clear()
        self.dirty_widgets.clear()
        self.invalidate_all = False
        self.committed_epoch = epoch
        return True

    def cancel(self) -> None:
        self.epoch += 1
        self.pending.clear()
        self.dirty_widgets.clear()
        self.invalidate_all = False
        self.committed_epoch = self.epoch
