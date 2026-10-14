"""Deterministic scroll input dispatch with inner-first residual chaining.

Native backends supply their current immutable viewport bindings and offsets.
No layout rectangle is mutated, and a delta is consumed at most once per host.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence

from .native_scroll_viewport import ScrollViewportBinding
from .scroll_offsets import ScrollOffset, consume_scroll_delta


@dataclass(frozen=True, slots=True)
class ScrollEventTarget:
    binding: ScrollViewportBinding
    offset: ScrollOffset


@dataclass(frozen=True, slots=True)
class ScrollEventStep:
    index: int
    offset: ScrollOffset
    consumed_x: float
    consumed_y: float


@dataclass(frozen=True, slots=True)
class ScrollEventDispatch:
    steps: tuple[ScrollEventStep, ...]
    remaining_x: float
    remaining_y: float


def dispatch_scroll_delta(
    targets: Sequence[ScrollEventTarget], *, delta_x: float = 0.0,
    delta_y: float = 0.0,
) -> ScrollEventDispatch:
    """Dispatch inner-to-outer, preserving residual amounts on both axes."""
    remaining_x, remaining_y = delta_x, delta_y
    steps: list[ScrollEventStep] = []
    for index, target in enumerate(targets):
        consumed = consume_scroll_delta(
            target.binding, target.offset,
            delta_x=remaining_x, delta_y=remaining_y,
        )
        steps.append(ScrollEventStep(
            index, consumed.offset,
            remaining_x - consumed.remaining_x,
            remaining_y - consumed.remaining_y,
        ))
        remaining_x, remaining_y = consumed.remaining_x, consumed.remaining_y
        if remaining_x == 0 and remaining_y == 0:
            break
    return ScrollEventDispatch(tuple(steps), remaining_x, remaining_y)


def scroll_key_delta(key: str, *, viewport_width: float, viewport_height: float,
                     offset: ScrollOffset | None = None,
                     maximum_x: float = 0.0, maximum_y: float = 0.0,
                     step: float = 40.0) -> tuple[float, float]:
    """Translate keyboard navigation into logical top-left movement.

    Home/End act on the vertical axis. Platform-specific modifiers remain the
    native adapter's responsibility.
    """
    movement = {
        "Left": (-step, 0.0), "Right": (step, 0.0),
        "Up": (0.0, -step), "Down": (0.0, step),
        "Page_Up": (0.0, -viewport_height), "Page_Down": (0.0, viewport_height),
        "PageUp": (0.0, -viewport_height), "PageDown": (0.0, viewport_height),
    }
    if key == "Home":
        return (0.0, -(offset.y if offset else 0.0))
    if key == "End":
        return (0.0, maximum_y - (offset.y if offset else 0.0))
    return movement.get(key, (0.0, 0.0))
