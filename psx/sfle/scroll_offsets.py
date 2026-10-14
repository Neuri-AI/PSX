"""Backend-neutral scroll offsets and viewport/content coordinate transforms.

SFLE rectangles are immutable layout results. Scroll state lives separately:
native hosts may move the content transform, but never rewrite layout boxes.
Offsets are logical top-left coordinates; native Y direction is an adapter concern.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from psx.sfle.native_scroll_viewport import ScrollViewportBinding


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True, slots=True)
class ScrollOffset:
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        _finite(self.x, "ScrollOffset.x")
        _finite(self.y, "ScrollOffset.y")


@dataclass(frozen=True, slots=True)
class ScrollConsumption:
    offset: ScrollOffset
    remaining_x: float
    remaining_y: float


def clamp_scroll_offset(binding: ScrollViewportBinding, offset: ScrollOffset) -> ScrollOffset:
    """Clamp to enabled axes and current content extent without mutating either box."""
    return ScrollOffset(
        min(max(0.0, offset.x), binding.overflow_x) if binding.clip_x else 0.0,
        min(max(0.0, offset.y), binding.overflow_y) if binding.clip_y else 0.0,
    )


def consume_scroll_delta(
    binding: ScrollViewportBinding,
    offset: ScrollOffset,
    *, delta_x: float = 0.0, delta_y: float = 0.0,
) -> ScrollConsumption:
    """Consume available movement; return residual deltas for a parent viewport.

    A disabled axis consumes nothing. Stale/out-of-bounds offsets are clamped
    before applying the event, so resizing cannot leak invalid visual state.
    """
    dx, dy = _finite(delta_x, "delta_x"), _finite(delta_y, "delta_y")
    start = clamp_scroll_offset(binding, offset)
    end = clamp_scroll_offset(binding, ScrollOffset(start.x + dx, start.y + dy))
    return ScrollConsumption(
        end, dx - (end.x - start.x), dy - (end.y - start.y),
    )


def content_to_viewport(
    binding: ScrollViewportBinding, offset: ScrollOffset,
    *, x: float, y: float,
) -> tuple[float, float]:
    """Project an SFLE content-local point into the viewport's parent space."""
    cx, cy = _finite(x, "x"), _finite(y, "y")
    clamped = clamp_scroll_offset(binding, offset)
    return binding.viewport.x + cx - clamped.x, binding.viewport.y + cy - clamped.y


def viewport_to_content(
    binding: ScrollViewportBinding, offset: ScrollOffset,
    *, x: float, y: float,
) -> tuple[float, float]:
    """Inverse projection; coordinates use the viewport's parent frame."""
    vx, vy = _finite(x, "x"), _finite(y, "y")
    clamped = clamp_scroll_offset(binding, offset)
    return vx - binding.viewport.x + clamped.x, vy - binding.viewport.y + clamped.y
