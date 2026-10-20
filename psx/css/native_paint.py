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


def foreground_rgba(computed: ComputedStyle | None) -> tuple[float, float, float, float] | None:
    """Return authored or explicitly inherited foreground, not a registry default."""
    if computed is None or "color" not in computed.specified:
        return None
    color = computed.properties["color"]
    if not isinstance(color, CssColor):
        raise TypeError("CSS foreground must be a validated color.")
    value = color.value.removeprefix("#")
    if len(value) in (3, 4):
        channels = [int(channel * 2, 16) for channel in value]
    else:
        channels = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
    if len(channels) == 3:
        channels.append(255)
    return tuple(channel / 255.0 for channel in channels)


def foreground_hex(computed: ComputedStyle | None) -> str | None:
    """Return opaque foreground for renderers unable to represent alpha."""
    rgba = foreground_rgba(computed)
    if rgba is None:
        return None
    if rgba[3] != 1.0:
        raise ValueError("Native CSS foreground paint currently requires opaque colors.")
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgba[:3])

def qt_semantic_stylesheet(computed: ComputedStyle | None) -> str:
    """Compose bounded authored paint into a local Qt stylesheet."""
    from psx.sfle.lengths import Length, LengthKind

    declarations: list[str] = []
    background = background_hex(computed)
    foreground = foreground_hex(computed)
    if background is not None:
        declarations.append(f"background-color: {background};")
    if foreground is not None:
        declarations.append(f"color: {foreground};")
    if computed is not None and "border-radius" in computed.specified:
        radius = computed.properties["border-radius"]
        if not isinstance(radius, Length) or radius.kind != LengthKind.PX:
            raise ValueError("Qt semantic border-radius currently requires px units.")
        declarations.append(f"border-radius: {radius.value:g}px;")
    return " ".join(declarations)
