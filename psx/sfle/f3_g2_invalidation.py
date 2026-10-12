"""F3-G2-C5 explicit measurement invalidation state and generation fences.

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

    def request(self, reason: str) -> int:
        if reason not in REASONS:
            raise ValueError(f"Unsupported SFLE measurement invalidation: {reason!r}")
        self.pending.add(reason)
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
        self.committed_epoch = epoch
        return True

    def cancel(self) -> None:
        self.epoch += 1
        self.pending.clear()
        self.committed_epoch = self.epoch
