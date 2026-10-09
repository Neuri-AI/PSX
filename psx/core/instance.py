"""Mutable mounted-instance state, intentionally separate from VNodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .events import EventSlot
from .vnode import VNode


@dataclass(slots=True)
class MountedInstance:
    node: VNode
    parent: "MountedInstance | None"
    handle: object | None = None
    children: list["MountedInstance"] = field(default_factory=list)
    event_slots: dict[str, tuple[EventSlot, object]] = field(default_factory=dict)
    hooks: list[object] = field(default_factory=list)
    hook_count: int | None = None
    ref: object | None = None
    contexts: dict[object, object] = field(default_factory=dict)
    attached: bool = False
    disposed: bool = False

    def native_handle(self) -> object:
        if self.handle is not None:
            return self.handle
        if len(self.children) != 1:
            raise RuntimeError("A component must currently render exactly one root node.")
        return self.children[0].native_handle()
