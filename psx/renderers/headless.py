"""Deterministic in-memory renderer for core tests and examples."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import RLock

from psx.core.events import EventSlot
from psx.core.vnode import VNode


# eq=False: handles compare by identity, so list.remove/in use the fast C
# identity path instead of a recursive field-by-field dataclass comparison.
@dataclass(slots=True, eq=False)
class HeadlessHandle:
    type: object
    props: dict[str, object]
    children: list["HeadlessHandle"] = field(default_factory=list)
    events: dict[str, EventSlot] = field(default_factory=dict)
    destroyed: bool = False


class HeadlessRenderer:
    """Records native-like operations without importing a UI toolkit."""

    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []
        self._pending: list[Callable[[], None]] = []
        self._lock = RLock()

    def create(self, node: VNode, parent: object | None) -> HeadlessHandle:
        handle = HeadlessHandle(node.type, dict(node.props))
        self.operations.append(("create", handle))
        return handle

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _handle(handle)
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        self.operations.append(("update", target, dict(changed), removed))

    def insert(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("insert", container, item, index))

    def move(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("move", container, item, index))

    def remove(self, parent: object, child: object) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        self.operations.append(("remove", container, item))

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        target = _handle(handle)
        target.events[event] = slot
        subscription = (target, event, slot)
        self.operations.append(("bind_event", target, event))
        return subscription

    def unbind_event(self, subscription: object) -> None:
        target, event, slot = subscription  # type: ignore[misc]
        if target.events.get(event) is slot:
            target.events.pop(event)
        self.operations.append(("unbind_event", target, event))

    def destroy(self, handle: object) -> None:
        target = _handle(handle)
        target.destroyed = True
        self.operations.append(("destroy", target))

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._pending.append(callback)

    def flush(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    return
                callback = self._pending.pop(0)
            callback()

    def run(self) -> int:
        self.flush()
        return 0


def _handle(value: object) -> HeadlessHandle:
    if not isinstance(value, HeadlessHandle):
        raise TypeError("HeadlessRenderer received a foreign handle.")
    return value