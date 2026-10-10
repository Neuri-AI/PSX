"""Shared portable Switch prop validation and normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import SWITCH_DEFAULTS, SWITCH_PROPS, validate_switch_props
from psx.core.errors import RendererCapabilityError

# Physical switch dimensions in logical pixels, shared by all backends.
SWITCH_SIZES: dict[str, tuple[int, int]] = {
    "small": (34, 20),
    "medium": (44, 26),
    "large": (56, 32),
}


def switch_props(props: Mapping[str, object]) -> dict[str, object]:
    """Return validated, defaulted portable props."""
    validate_switch_props(props)
    return {**SWITCH_DEFAULTS, **props}


def updated_switch_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    """Merge a VDOM update and restore defaults for removed props."""
    unknown = (set(changed) | set(removed)) - SWITCH_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Switch props: {', '.join(sorted(unknown))}"
        )
    merged = {name: value for name, value in current.items() if name not in removed}
    merged.update(changed)
    return switch_props(merged)


def hex_rgb(color: str) -> tuple[int, int, int]:
    """Decode a validated six-digit hexadecimal color."""
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
