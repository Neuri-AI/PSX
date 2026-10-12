"""C5 native intrinsic measurement cache.

Native widgets are held by identity, not reused node IDs. Cache entries are
published only after a successful SFLE geometry/readback transaction. Explicit
semantic invalidation clears native measurements; ordinary reconciliation
remeasures only leaves with changed declarative props or viewport constraints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from psx.sfle.model import MeasuredBox


@dataclass(slots=True)
class NativeIntrinsicCache:
    entries: dict[int, tuple[object, object, object]] = field(default_factory=dict)
    last_measured: set[int] = field(default_factory=set)
    width_entries: dict[tuple[int, float], tuple[object, object, object]] = field(default_factory=dict)
    last_width_measured: set[tuple[int, float]] = field(default_factory=set)

    def begin(self, *, invalidate_all: bool = False) -> "NativeMeasurementRound":
        return NativeMeasurementRound(self, invalidate_all=invalidate_all)

    def clear(self) -> None:
        self.entries.clear()
        self.last_measured.clear()
        self.width_entries.clear()
        self.last_width_measured.clear()


@dataclass(slots=True)
class NativeMeasurementRound:
    cache: NativeIntrinsicCache
    invalidate_all: bool = False
    updated: dict[int, tuple[object, object, object]] = field(default_factory=dict)
    measured: set[int] = field(default_factory=set)
    updated_width: dict[tuple[int, float], tuple[object, object, object]] = field(default_factory=dict)
    measured_width: set[tuple[int, float]] = field(default_factory=set)

    def read(
        self,
        *,
        widget: object,
        props: object,
        constraints: object,
        node_id: str,
        generation: int,
        measure: Callable[[], MeasuredBox],
    ) -> MeasuredBox:
        identity = id(widget)
        old = self.cache.entries.get(identity)
        if (not self.invalidate_all and old is not None
                and old[0] == props and old[1] == constraints):
            intrinsic = old[2]
        else:
            intrinsic = measure().intrinsic
            self.measured.add(identity)
        self.updated[identity] = (props, constraints, intrinsic)
        return MeasuredBox(node_id, intrinsic, constraints, generation)

    def read_width(
        self,
        *,
        widget: object,
        props: object,
        constraints: object,
        width: float,
        measure: Callable[[], object],
    ) -> object:
        key = (id(widget), width)
        previous = self.cache.width_entries.get(key)
        if (not self.invalidate_all and previous is not None
                and previous[0] == props and previous[1] == constraints):
            intrinsic = previous[2]
        else:
            intrinsic = measure()
            self.measured_width.add(key)
        self.updated_width[key] = (props, constraints, intrinsic)
        return intrinsic

    def publish(self) -> None:
        self.cache.entries = self.updated
        self.cache.last_measured = self.measured
        self.cache.width_entries = self.updated_width
        self.cache.last_width_measured = self.measured_width
