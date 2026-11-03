"""Mutable mounted-instance state, intentionally separate from VNodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .events import EventSlot
from .vnode import VNode


@dataclass(slots=True)
class MountedInstance:
    # Native handle that the parent layout most recently inserted for this
    # instance. It normally equals ``native_handle()``, but can diverge when
    # a component virtual node changes the type of its only child (for
    # example ``Row`` -> ``Column``): the MountedInstance survives, but the
    # widget it represents underneath changes. The parent layout must be told
    # to replace the old widget with the new one.
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
    # Logical component lifetime is intentionally independent from whether its
    # native subtree is currently attached to a toolkit parent.  Viewport
    # materialization only toggles this flag; it never disposes hooks, refs or
    # the declarative identity of the instance.
    native_materialized: bool = True
    # A suspended logical host owns no native resource. Unlike an unattached
    # handle, it must not receive native updates or create native children.
    native_suspended: bool = False
    structural_binding: object | None = None
    _placed_handle: object | None = None

    def native_handle(self) -> object:
        if self.handle is not None:
            return self.handle
        if len(self.children) != 1:
            raise RuntimeError("A component must currently render exactly one root node.")
        return self.children[0].native_handle()
