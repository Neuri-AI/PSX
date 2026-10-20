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
    if computed is not None and "border-color" in computed.specified:
        from psx.sfle.lengths import LengthKind
        width = computed.properties["border-width"]
        if width.kind != LengthKind.PX:
            raise ValueError("Qt border paint requires a pixel border-width.")
        if width.value > 0:
            raw_color = computed.properties["border-color"]
            if not isinstance(raw_color, CssColor):
                raise TypeError("CSS border color must be validated.")
            value = raw_color.value.removeprefix("#")
            if len(value) in (3, 4):
                channels = [int(c * 2, 16) for c in value]
            else:
                channels = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
            if len(channels) == 3:
                channels.append(255)
            if channels[3] != 255:
                raise ValueError("Qt border paint requires opaque colors.")
            border = "#" + "".join(f"{c:02x}" for c in channels[:3])
            declarations.append(f"border: {width.value:g}px solid {border};")
    if computed is not None and "border-radius" in computed.specified:
        radius = computed.properties["border-radius"]
        if not isinstance(radius, Length) or radius.kind != LengthKind.PX:
            raise ValueError("Qt semantic border-radius currently requires px units.")
        declarations.append(f"border-radius: {radius.value:g}px;")
    if computed is not None:
        from psx.sfle.lengths import Length, LengthKind
        for css_name, qss_name in (("font-family", "font-family"), ("font-size", "font-size")):
            if css_name not in computed.specified:
                continue
            value = computed.properties[css_name]
            if css_name == "font-family":
                if not isinstance(value, str) or not value or any(c in value for c in '{};:"\\\\'):
                    raise ValueError("Invalid native Qt font-family.")
                declarations.append(f'font-family: "{value}";')
            else:
                if not isinstance(value, Length) or value.kind != LengthKind.PX or value.value <= 0:
                    raise ValueError("Qt font-size requires positive px units.")
                declarations.append(f"font-size: {value.value:g}px;")
        if "font-weight" in computed.specified:
            weight = computed.properties["font-weight"]
            if type(weight) is not int or weight not in range(100, 1000, 100):
                raise ValueError("Qt font-weight requires normalized CSS weight.")
            declarations.append(f"font-weight: {weight};")
        if "text-align" in computed.specified:
            alignment = computed.properties["text-align"]
            if alignment not in ("left", "right", "center", "start", "end"):
                raise ValueError("Qt semantic text-align does not support justify.")
            declarations.append(f"text-align: {'left' if alignment == 'start' else 'right' if alignment == 'end' else alignment};")
    return " ".join(declarations)

def border_rgba(computed: ComputedStyle | None) -> tuple[float, float, float, float] | None:
    """Resolve explicitly authored border paint, independent of its geometry."""
    if computed is None or "border-color" not in computed.specified:
        return None
    value = computed.properties["border-color"]
    if not isinstance(value, CssColor):
        raise TypeError("CSS border-color must be validated.")
    color = value.value.removeprefix("#")
    if len(color) in (3, 4):
        channels = [int(character * 2, 16) for character in color]
    else:
        channels = [int(color[index:index + 2], 16) for index in range(0, len(color), 2)]
    if len(channels) == 3:
        channels.append(255)
    return tuple(channel / 255 for channel in channels)

def native_text_typography(computed: ComputedStyle | None, *, alpha: bool = False) -> dict[str, object]:
    """Project explicitly authored native Text values without altering component props."""
    from psx.sfle.lengths import Length, LengthKind

    if computed is None:
        return {}
    result: dict[str, object] = {}
    if "color" in computed.specified:
        rgba = foreground_rgba(computed)
        if rgba is not None:
            if alpha:
                result["color"] = rgba
            else:
                result["color"] = foreground_hex(computed)
    if "font-family" in computed.specified:
        family = computed.properties["font-family"]
        if not isinstance(family, str) or not family.strip():
            raise ValueError("CSS font-family must be validated.")
        result["font-family"] = family
    if "font-size" in computed.specified:
        size = computed.properties["font-size"]
        if not isinstance(size, Length) or size.kind is not LengthKind.PX or size.value <= 0:
            raise ValueError("Native Text font-size requires positive px units.")
        result["font-size"] = size.value
    if "font-weight" in computed.specified:
        weight = computed.properties["font-weight"]
        if type(weight) is not int or weight not in range(100, 1000, 100):
            raise ValueError("Native Text font-weight requires normalized CSS weight.")
        result["font-weight"] = weight
    if "text-align" in computed.specified:
        alignment = computed.properties["text-align"]
        if alignment not in ("left", "right", "center", "start", "end"):
            raise ValueError("Native Text does not support justify alignment.")
        result["text-align"] = {"start": "left", "end": "right"}.get(alignment, alignment)
    if "line-height" in computed.specified:
        raise ValueError("Native Text line-height is not certified by the text metrics bridge.")
    return result
