"""Operation-specific behavioral oracles for F3-G2 native certification.

C2 supplies the assertions. C3/C4/C5 drivers must perform the operation on
a real backend, capture before/after, and call the corresponding oracle.
An oracle's existence is NOT evidence that a native operation has passed.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class Observation:
    native_identity: object | None
    mounted: bool
    rect: tuple[float, float, float, float] | None
    state: object = None
    order: tuple[str, ...] = ()
    events: tuple[object, ...] = ()
    callback_identity: object = None
    owner: str = "psx"
    disposed: bool = False
    revision: int = 0
    remeasure_count: int = 0
    mutation_failed: bool = False


def create(before: Observation | None, after: Observation) -> None:
    assert before is None or not before.mounted
    assert after.mounted and not after.disposed
    assert after.native_identity is not None and after.rect is not None
    assert after.rect[2] >= 0 and after.rect[3] >= 0


def update(before: Observation, after: Observation) -> None:
    assert before.mounted and after.mounted
    assert before.native_identity == after.native_identity
    assert before.state != after.state, "Test driver must apply a state change"


def reorder(before: Observation, after: Observation) -> None:
    assert before.mounted and after.mounted
    assert before.native_identity == after.native_identity
    assert before.order and after.order and before.order != after.order
    assert sorted(before.order) == sorted(after.order)


def unmount(before: Observation, after: Observation) -> None:
    assert before.mounted and not after.mounted
    assert before.native_identity == after.native_identity
    assert after.disposed, "Owned native resources must be disposed"


def event_rebind(before: Observation, after: Observation) -> None:
    assert before.mounted and after.mounted
    assert before.native_identity == after.native_identity
    assert before.callback_identity != after.callback_identity
    assert len(after.events) == len(before.events) + 1
    assert after.events[-1] == after.callback_identity


def borrowed_ownership(before: Observation, after: Observation) -> None:
    assert before.owner == after.owner == "caller"
    assert before.native_identity == after.native_identity
    assert not after.disposed, "PSX must not destroy caller-owned widgets"


def rollback(before: Observation, after: Observation) -> None:
    assert after.mutation_failed
    assert after.native_identity == before.native_identity
    assert after.rect == before.rect
    assert after.state == before.state


def invalidation(before: Observation, after: Observation) -> None:
    assert before.mounted and after.mounted
    assert before.native_identity == after.native_identity
    assert after.revision > before.revision
    assert after.remeasure_count > before.remeasure_count


ORACLES: MappingProxyType[str, Callable[..., None]] = MappingProxyType({
    "create": create, "update": update, "reorder": reorder,
    "unmount": unmount, "event_rebind": event_rebind,
    "borrowed_ownership": borrowed_ownership, "rollback": rollback,
    "invalidation": invalidation,
})
