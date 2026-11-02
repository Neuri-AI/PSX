"""Owner-thread priority and idle reconciliation for viewport resize bursts.

P0: visible/entering viewport (always committed by the worksets).
P1: unsafe or structurally dependent (always solved and committed).
P2: previously accepted, fully offscreen subtrees (deferred during resize).

The coordinator never guesses CSS geometry or paints offscreen widgets.
A monotonic resize generation invalidates every queued idle callback. During
settlement, a bounded number of P2 groups per event-loop turn are promoted
to native commit, with failed batches rolled back. Rust remains the sole
authority for every solved rectangle.
"""
from __future__ import annotations

from enum import IntEnum


class ViewportPriority(IntEnum):
    VISIBLE = 0
    STRUCTURAL = 1
    DEFERRED = 2


def classify_viewport_priority(*, certified: bool, safe: bool,
                               old_top: float, old_bottom: float,
                               new_top: float, new_bottom: float,
                               viewport_top: float,
                               viewport_height: float,
                               overscan: float = 96.0) -> ViewportPriority:
    """Fail closed: both accepted and target bounds must be outside."""
    from math import isfinite
    values = (old_top, old_bottom, new_top, new_bottom,
              viewport_top, viewport_height, overscan)
    if not all(isfinite(value) for value in values) or viewport_height <= 0 or overscan < 0:
        return ViewportPriority.STRUCTURAL
    low, high = viewport_top - overscan, viewport_top + viewport_height + overscan
    if ((old_top < high and old_bottom > low)
            or (new_top < high and new_bottom > low)):
        return ViewportPriority.VISIBLE
    if not certified or not safe or old_bottom < old_top or new_bottom < new_top:
        return ViewportPriority.STRUCTURAL
    # Crossing from above to below can intersect the viewport during a
    # resize. Reusing the earlier native location is then unsafe.
    if not ((old_top >= high and new_top >= high)
            or (old_bottom <= low and new_bottom <= low)):
        return ViewportPriority.STRUCTURAL
    return ViewportPriority.DEFERRED


class ViewportResizeCoordinator:
    """No timers, native handles or background threads: toolkit owns scheduling."""

    def __init__(self, *, batch_size: int = 64) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.generation = 0
        self.latest_size = None
        self.active = False
        self.settling = False
        self._accepted: set[tuple[int, str]] = set()
        self._candidate: set[tuple[int, str]] = set()
        self._remaining = 0
        self._batch_open = False

    def resize(self, size: tuple[float, float]) -> int:
        if size != self.latest_size:
            self.latest_size = size
            self.generation += 1
            self.active = True
            self.settling = False
            self._accepted.clear()
            self._candidate.clear()
            self._remaining = 0
            self._batch_open = False
        return self.generation

    def begin_settlement(self, generation: int) -> bool:
        if generation != self.generation or not self.active:
            return False
        self.active = False
        self.settling = True
        self._candidate.clear()
        self._remaining = 0
        self._batch_open = False
        return True

    def begin_batch(self, generation: int) -> bool:
        if generation != self.generation or not self.settling:
            return False
        self._candidate.clear()
        self._remaining = 0
        self._batch_open = True
        return True

    def promote(self, workset: object, root_id: str) -> bool:
        """Promote at most N certified P2 groups this UI turn."""
        if not self.settling or not self._batch_open:
            return False
        key = (id(workset), root_id)
        if key in self._accepted:
            return False
        if len(self._candidate) < self.batch_size:
            self._candidate.add(key)
            return True
        self._remaining += 1
        return False

    def finish_batch(self, *, success: bool) -> bool:
        if not self.settling or not self._batch_open:
            return False
        self._batch_open = False
        if not success:
            self._candidate.clear()
            self.settling = False
            return False
        self._accepted.update(self._candidate)
        self._candidate.clear()
        more = self._remaining > 0
        if not more:
            self.settling = False
            self._accepted.clear()
        return more

    def cancel(self) -> None:
        self.generation += 1
        self.active = False
        self.settling = False
        self._accepted.clear()
        self._candidate.clear()
        self._remaining = 0
