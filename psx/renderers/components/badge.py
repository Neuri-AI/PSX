"""Shared presentation tokens, normalization and sizing for portable Badge."""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import BADGE_DEFAULTS, BADGE_PROPS, validate_badge_props
from psx.core.errors import RendererCapabilityError

BADGE_PALETTE: dict[str, tuple[str, str]] = {
    "neutral": ("#374151", "#6B7280"),
    "success": ("#15803D", "#15803D"),
    "warning": ("#A16207", "#A16207"),
    "danger": ("#B91C1C", "#B91C1C"),
    "info": ("#1D4ED8", "#1D4ED8"),
}

# Font size, horizontal inset, vertical inset in logical pixels.
BADGE_SIZES: dict[str, tuple[int, int, int]] = {
    "small": (11, 6, 2),
    "medium": (12, 8, 4),
    "large": (14, 10, 6),
}


def badge_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_badge_props(props)
    return {**BADGE_DEFAULTS, **props}


def updated_badge_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - BADGE_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Badge props: {', '.join(sorted(unknown))}"
        )
    merged = {name: value for name, value in current.items() if name not in removed}
    merged.update(changed)
    return badge_props(merged)


def badge_style(props: Mapping[str, object]) -> tuple[str, str, str, int, int, int]:
    """Return foreground, background, stroke, font size, horizontal and vertical padding."""
    background, accent = BADGE_PALETTE[props["variant"]]
    if props["appearance"] == "filled":
        foreground, stroke = "#FFFFFF", background
    else:
        foreground, background, stroke = accent, "", accent
    if not props["enabled"]:
        # A deliberately stable, theme-independent disabled palette.
        foreground, background, stroke = "#6B7280", "#E5E7EB", "#9CA3AF"
        if props["appearance"] == "outline":
            background = ""
    font_size, horizontal, vertical = BADGE_SIZES[props["size"]]
    return foreground, background, stroke, font_size, horizontal, vertical


def hex_rgba(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    return (
        int(value[1:3], 16) / 255,
        int(value[3:5], 16) / 255,
        int(value[5:7], 16) / 255,
        alpha,
    )
