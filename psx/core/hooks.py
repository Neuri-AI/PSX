"""Ordered function-component hooks. No GUI or integration dependency lives here."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from .errors import HookOrderError, ThreadViolationError
from .instance import MountedInstance
from .scheduler import Scheduler

T = TypeVar("T")


@dataclass(slots=True)
class Ref(Generic[T]):
    current: T | None = None


@dataclass(slots=True)
class _RenderContext:
    instance: MountedInstance
    scheduler: Scheduler
    index: int = 0


@dataclass(slots=True)
class _StateSlot(Generic[T]):
    value: T


@dataclass(slots=True)
class _RefSlot(Generic[T]):
    ref: Ref[T]


@dataclass(slots=True)
class _EffectSlot:
    deps: tuple[object, ...] | None
    callback: Callable[[], Callable[[], None] | None]
    cleanup: Callable[[], None] | None = None
    pending: bool = True


_CURRENT: ContextVar[_RenderContext | None] = ContextVar("psx_current_render", default=None)


def begin_render(instance: MountedInstance, scheduler: Scheduler) -> object:
    return _CURRENT.set(_RenderContext(instance, scheduler))


def end_render(token: object) -> None:
    context = _require_context()
    expected = getattr(context.instance, "hook_count", None)
    if expected is None:
        context.instance.hook_count = context.index
    elif expected != context.index:
        _CURRENT.reset(token)  # type: ignore[arg-type]
        raise HookOrderError(
            f"Component changed hook count from {expected} to {context.index}."
        )
    _CURRENT.reset(token)  # type: ignore[arg-type]


def abort_render(token: object) -> None:
    _CURRENT.reset(token)  # type: ignore[arg-type]


def use_state(initial: T | Callable[[], T]) -> tuple[T, Callable[[T | Callable[[T], T]], None]]:
    context, index = _next_slot("state")
    slots = context.instance.hooks
    if index == len(slots):
        value = initial() if callable(initial) else initial
        slots.append(_StateSlot(value))
    slot = slots[index]
    if not isinstance(slot, _StateSlot):
        raise HookOrderError("Hook kind changed at position %d." % index)

    def set_state(next_value: T | Callable[[T], T]) -> None:
        if _CURRENT.get() is not None:
            raise ThreadViolationError("State updates during component rendering are not supported.")
        if context.instance.disposed:
            return
        previous = slot.value
        resolved = next_value(previous) if callable(next_value) else next_value
        if _state_equal(previous, resolved):
            return
        slot.value = resolved
        context.scheduler.mark_dirty(context.instance)

    return cast(T, slot.value), set_state


def use_ref(initial: T | None = None) -> Ref[T]:
    context, index = _next_slot("ref")
    slots = context.instance.hooks
    if index == len(slots):
        slots.append(_RefSlot(Ref(initial)))
    slot = slots[index]
    if not isinstance(slot, _RefSlot):
        raise HookOrderError("Hook kind changed at position %d." % index)
    return cast(Ref[T], slot.ref)


def use_effect(
    callback: Callable[[], Callable[[], None] | None], dependencies: Sequence[object] | None = None
) -> None:
    context, index = _next_slot("effect")
    deps = None if dependencies is None else tuple(dependencies)
    slots = context.instance.hooks
    if index == len(slots):
        slot = _EffectSlot(deps=deps, callback=callback)
        slots.append(slot)
    else:
        slot = slots[index]
        if not isinstance(slot, _EffectSlot):
            raise HookOrderError("Hook kind changed at position %d." % index)
        slot.pending = dependencies is None or not _dependencies_equal(slot.deps, deps)
        slot.deps = deps
        slot.callback = callback
    if slot.pending:
        context.scheduler.queue_effect(context.instance, index, lambda: _run_effect(context.instance, slot))


def dispose_hooks(instance: MountedInstance) -> None:
    """Dispose effects in reverse registration order before native destruction."""
    for slot in reversed(instance.hooks):
        if isinstance(slot, _EffectSlot) and slot.cleanup is not None:
            cleanup, slot.cleanup = slot.cleanup, None
            cleanup()
    instance.hooks.clear()


def provide_context(key: object, value: object) -> None:
    """Attach an explicit provider value to the component currently rendering."""
    _require_context().instance.contexts[key] = value


def use_context(key: object) -> object:
    """Look up the nearest explicit provider without creating a global singleton."""
    instance = _require_context().instance
    while instance is not None:
        if key in instance.contexts:
            return instance.contexts[key]
        instance = instance.parent
    raise LookupError("No matching PSX provider exists for this component.")


def _run_effect(instance: MountedInstance, slot: _EffectSlot) -> None:
    if instance.disposed or not slot.pending:
        return
    if slot.cleanup is not None:
        cleanup, slot.cleanup = slot.cleanup, None
        cleanup()
    slot.pending = False
    cleanup = slot.callback()
    if cleanup is not None and not callable(cleanup):
        raise TypeError("use_effect callback must return a cleanup callable or None.")
    slot.cleanup = cleanup


def _next_slot(expected: str) -> tuple[_RenderContext, int]:
    context = _require_context()
    index = context.index
    context.index += 1
    return context, index


def _require_context() -> _RenderContext:
    context = _CURRENT.get()
    if context is None:
        raise HookOrderError("PSX hooks may only be called while a function component renders.")
    return context


def _dependencies_equal(old: tuple[object, ...] | None, new: tuple[object, ...] | None) -> bool:
    if old is None or new is None or len(old) != len(new):
        return False
    return all(_state_equal(previous, current) for previous, current in zip(old, new))


def _state_equal(old: object, new: object) -> bool:
    scalar_types = (type(None), bool, int, float, str, bytes)
    if type(old) in scalar_types and type(new) is type(old):
        return old == new
    return old is new
