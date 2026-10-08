"""Pure-description reconciliation followed by renderer mutations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from psx.renderers.protocol import Renderer

from .errors import DuplicateKeyError
from .events import EventSlot
from .hooks import Ref, abort_render, begin_render, dispose_hooks, end_render
from .instance import MountedInstance
from .scheduler import Scheduler
from .vnode import NodeKind, VNode

_EVENT_PREFIX = "on_"
_RUNTIME_PROPS = frozenset({"ref"})


class Reconciler:
    """Owns one mounted root and applies minimal reasonable renderer operations."""

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer
        self.root: MountedInstance | None = None
        self._is_rendering = False
        self._pending_refs: list[tuple[MountedInstance, Ref[object] | None]] = []
        self.scheduler = Scheduler(renderer.schedule_ui, self._flush_dirty)

    def render(self, node: VNode) -> MountedInstance:
        """Mount or update the single root description."""
        if self._is_rendering:
            raise RuntimeError("PSX rendering is not re-entrant.")
        self._is_rendering = True
        try:
            if self.root is None:
                self.root = self._mount(node, None)
            else:
                self.root = self._reconcile(self.root, node, None)
            root = self.root
        finally:
            self._is_rendering = False
        self._commit_refs()
        self.scheduler.run_effects()
        assert root is not None
        return root

    def unmount(self) -> None:
        if self.root is not None:
            self._unmount(self.root, detach=False)
            self.root = None

    def _mount(self, node: VNode, parent: MountedInstance | None) -> MountedInstance:
        instance = MountedInstance(node=node, parent=parent)
        try:
            if node.kind is NodeKind.COMPONENT:
                rendered = self._evaluate_component(instance)
                instance.children = [self._mount(rendered, instance)]
                return instance

            instance.handle = self.renderer.create(
                _without_runtime_props(node), parent.native_handle() if parent and parent.handle else None
            )
            self._queue_ref(instance, node.props.get("ref"))
            self._sync_events(instance, {}, node.props)
            _validate_keys(node.children)
            instance.children = [self._mount(child, instance) for child in node.children]
            self._place_children(instance, [], instance.children)
            return instance
        except Exception:
            self._unmount(instance, detach=False)
            raise

    def _reconcile(
        self, old: MountedInstance, node: VNode, parent: MountedInstance | None
    ) -> MountedInstance:
        if not _compatible(old.node, node):
            self._unmount(old, detach=old.attached)
            return self._mount(node, parent)

        previous_node = old.node
        old.node = node
        if node.kind is NodeKind.COMPONENT:
            rendered = self._evaluate_component(old)
            previous = old.children[0]
            old.children = [self._reconcile(previous, rendered, old)]
            return old

        assert old.handle is not None
        changed, removed = _prop_delta(previous_node.props, node.props)
        if previous_node.props.get("ref") is not node.props.get("ref"):
            self._queue_ref(old, node.props.get("ref"))
        self._sync_events(old, previous_node.props, node.props)
        if changed or removed:
            self.renderer.update(old.handle, changed, removed)
        previous_children = old.children
        next_children = self._reconcile_children(old, previous_children, node.children)
        old.children = next_children
        self._place_children(old, previous_children, next_children)
        return old

    def _reconcile_children(
        self, parent: MountedInstance, old_children: list[MountedInstance], new_nodes: tuple[VNode, ...]
    ) -> list[MountedInstance]:
        _validate_keys(new_nodes)
        _validate_keys(tuple(child.node for child in old_children))
        keyed = {child.node.key: child for child in old_children if child.node.key is not None}
        unkeyed = [child for child in old_children if child.node.key is None]
        used: set[int] = set()
        unkeyed_index = 0
        result: list[MountedInstance] = []
        for node in new_nodes:
            candidate: MountedInstance | None
            if node.key is not None:
                candidate = keyed.get(node.key)
            else:
                candidate = unkeyed[unkeyed_index] if unkeyed_index < len(unkeyed) else None
                unkeyed_index += 1
            if candidate is not None:
                used.add(id(candidate))
                result.append(self._reconcile(candidate, node, parent))
            else:
                result.append(self._mount(node, parent))
        for child in old_children:
            if id(child) not in used:
                self._unmount(child, detach=child.attached)
        return result

    def _place_children(
        self,
        parent: MountedInstance,
        previous: list[MountedInstance],
        desired: list[MountedInstance],
    ) -> None:
        if parent.handle is None:
            return
        current = [child for child in previous if not child.disposed and child.attached]
        # Walking ``desired`` left to right, ``current[:index]`` always equals
        # ``desired[:index]`` and the rest is the not-yet-placed old children in
        # their original relative order. So instead of simulating the list
        # (O(N) ``in``/``remove``/``insert`` per child), track the unplaced old
        # children by identity and keep a cursor to the first of them: O(N) total
        # with exactly the same sequence of renderer operations.
        pending = {id(child) for child in current}
        cursor = 0
        for index, child in enumerate(desired):
            handle = child.native_handle()
            while cursor < len(current) and id(current[cursor]) not in pending:
                cursor += 1
            if cursor < len(current) and current[cursor] is child:
                pending.discard(id(child))
                cursor += 1
                continue
            if id(child) in pending:
                self.renderer.move(parent.handle, handle, index)
                pending.discard(id(child))
            else:
                self.renderer.insert(parent.handle, handle, index)
                child.attached = True

    def _sync_events(
        self,
        instance: MountedInstance,
        old_props: Mapping[str, object],
        new_props: Mapping[str, object],
    ) -> None:
        assert instance.handle is not None
        names = {name for name in old_props if _is_event(name)} | {
            name for name in new_props if _is_event(name)
        }
        for name in names:
            callback = new_props.get(name)
            if callback is not None and not callable(callback):
                raise TypeError(f"{name} must be callable or None.")
            previous = instance.event_slots.get(name)
            if callback is None:
                if previous is not None:
                    previous[0].dispose()
                    self.renderer.unbind_event(previous[1])
                    instance.event_slots.pop(name, None)
                continue
            if previous is None:
                slot = EventSlot(cast(object, callback))
                subscription = self.renderer.bind_event(instance.handle, name, slot)
                instance.event_slots[name] = (slot, subscription)
            else:
                previous[0].update(cast(object, callback))

    def _unmount(self, instance: MountedInstance, *, detach: bool) -> None:
        if instance.disposed:
            return
        instance.disposed = True
        native_handle = instance.native_handle() if detach and instance.handle is None else instance.handle
        if detach and native_handle is not None and instance.parent is not None and instance.parent.handle is not None:
            self.renderer.remove(instance.parent.handle, native_handle)
        # Slots become inert before any native removal can result in stale callbacks.
        for slot, subscription in tuple(instance.event_slots.values()):
            slot.dispose()
            self.renderer.unbind_event(subscription)
        instance.event_slots.clear()
        if isinstance(instance.ref, Ref):
            instance.ref.current = None
        dispose_hooks(instance)
        for child in reversed(instance.children):
            self._unmount(child, detach=False)
        if instance.handle is not None:
            self.renderer.destroy(instance.handle)

    def _evaluate_component(self, instance: MountedInstance) -> VNode:
        component = instance.node.type
        props = dict(instance.node.props)
        token = begin_render(instance, self.scheduler)
        try:
            result = component.render(**props)  # type: ignore[union-attr]
        except Exception:
            abort_render(token)
            raise
        end_render(token)
        if not isinstance(result, VNode):
            raise TypeError(f"Component {component.name} must return a VNode.")  # type: ignore[union-attr]
        return result

    def _flush_dirty(self, dirty: tuple[MountedInstance, ...]) -> None:
        """Called by the renderer's UI loop after coalescing state updates."""
        if self._is_rendering:
            raise RuntimeError("Scheduler attempted to flush during rendering.")
        self._is_rendering = True
        try:
            for instance in dirty:
                if instance.disposed or instance.node.kind is not NodeKind.COMPONENT:
                    continue
                rendered = self._evaluate_component(instance)
                previous = instance.children[0]
                instance.children = [self._reconcile(previous, rendered, instance)]
        finally:
            self._is_rendering = False
        self._commit_refs()
        self.scheduler.run_effects()

    def _queue_ref(self, instance: MountedInstance, value: object | None) -> None:
        if value is not None and not isinstance(value, Ref):
            raise TypeError("ref must be a Ref created by use_ref().")
        self._pending_refs.append((instance, value))

    def _commit_refs(self) -> None:
        pending, self._pending_refs = self._pending_refs, []
        for instance, ref in pending:
            if isinstance(instance.ref, Ref) and instance.ref is not ref:
                instance.ref.current = None
            instance.ref = ref
            if ref is not None and not instance.disposed:
                handle = instance.native_handle()
                # Native refs deliberately expose the framework widget rather
                # than PSX's private renderer handle.
                ref.current = getattr(handle, "widget", handle) if instance.node.kind is NodeKind.NATIVE else handle


def _compatible(old: VNode, new: VNode) -> bool:
    return old.kind is new.kind and old.type == new.type and old.key == new.key


def _is_event(name: str) -> bool:
    return name.startswith(_EVENT_PREFIX)


def _prop_delta(
    old: Mapping[str, object], new: Mapping[str, object]
) -> tuple[dict[str, object], frozenset[str]]:
    changed = {
        name: value
        for name, value in new.items()
        if not _is_event(name)
        and name not in _RUNTIME_PROPS
        and (name not in old or old[name] is not value and old[name] != value)
    }
    removed = frozenset(
        name for name in old if name not in new and not _is_event(name) and name not in _RUNTIME_PROPS
    )
    return changed, removed


def _validate_keys(nodes: tuple[VNode, ...]) -> None:
    seen: set[str | int] = set()
    for node in nodes:
        if node.key is not None:
            if node.key in seen:
                raise DuplicateKeyError(f"Duplicate key among siblings: {node.key!r}")
            seen.add(node.key)


def _without_runtime_props(node: VNode) -> VNode:
    if not any(name in node.props for name in _RUNTIME_PROPS):
        return node
    props = {name: value for name, value in node.props.items() if name not in _RUNTIME_PROPS}
    return VNode(node.kind, node.type, node.key, props, node.children)