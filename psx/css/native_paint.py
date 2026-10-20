"""Bounded CSS paint projection without native widget dependencies.

Only explicitly specified paint declarations are exported. Inherited CSS
foregrounds are emitted only when explicitly authored on an ancestor or the
node itself, never from the registry's artificial default foreground.
"""
from __future__ import annotations

from .cascade import ComputedStyle
from .visual_values import CssColor


def background_rgba(computed: ComputedStyle | None) -> tuple[float, float, float, float] | None:
    """Return normalized RGBA for explicitly authored CSS background-color."""
    if computed is None or "background-color" not in computed.specified:
        return None
    raw = computed.properties["background-color"]
    if not isinstance(raw, CssColor):
        raise TypeError("CSS background must be a validated color.")
    value = raw.value.removeprefix("#")
    if len(value) in (3, 4):
        channels = [int(c * 2, 16) for c in value]
    else:
        channels = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
    if len(channels) == 3:
        channels.append(255)
    return tuple(c / 255.0 for c in channels)


def background_hex(computed: ComputedStyle | None) -> str | None:
    """Return #RRGGBB for opaque CSS backgrounds; reject silent alpha loss."""
    rgba = background_rgba(computed)
    if rgba is None:
        return None
    if rgba[3] != 1.0:
        raise ValueError("Native CSS background paint currently requires opaque colors.")
    return "#" + "".join(f"{round(v * 255):02x}" for v in rgba[:3])
