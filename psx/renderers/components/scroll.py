"""Backend-neutral Scroll normalization, sizing helpers and wheel chaining."""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import SCROLL_DEFAULTS, SCROLL_PROPS, validate_scroll_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.column import normalize_padding


def scroll_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_scroll_props(props)
    return {**SCROLL_DEFAULTS, **props}


def updated_scroll_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - SCROLL_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Scroll props: {', '.join(sorted(unknown))}"
        )
    result = {k: v for k, v in current.items() if k not in removed}
    result.update(changed)
    return scroll_props(result)


def scroll_axes(direction: str) -> tuple[bool, bool]:
    """Return (horizontal, vertical) permissions."""
    return direction in ("horizontal", "both"), direction in ("vertical", "both")


def scroll_padding(props: Mapping[str, object]) -> tuple[int, int, int, int]:
    return normalize_padding(props["padding"])


def consume_scroll(position: float, maximum: float, delta: float) -> tuple[float, float]:
    """Return (new position, unconsumed delta); positive deltas move forward."""
    next_position = min(maximum, max(0.0, position + delta))
    return next_position, delta - (next_position - position)
