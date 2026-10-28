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

def native_side_border_styles(computed: ComputedStyle | None) -> tuple[str, ...]:
    """Validated per-side solid borders for native Qt widget-local QSS."""
    from psx.sfle.lengths import Length, LengthKind
    if computed is None:
        return ()
    result = []
    for side in ("top", "right", "bottom", "left"):
        width_key = f"border-{side}-width"
        color_key = f"border-{side}-color"
        if width_key not in computed.specified and color_key not in computed.specified:
            continue
        width = computed.properties[width_key] if width_key in computed.specified else computed.properties["border-width"]
        color = computed.properties[color_key] if color_key in computed.specified else computed.properties["border-color"]
        if not isinstance(width, Length) or width.kind is not LengthKind.PX or width.value < 0:
            raise ValueError("Native border sides require nonnegative pixel widths.")
        if not isinstance(color, CssColor):
            raise TypeError("Native border sides require validated CSS colors.")
        rgba = color.value.lstrip("#")
        if len(rgba) in (4, 8) and (rgba[-1] != "f" if len(rgba) == 4 else rgba[-2:] != "ff"):
            raise ValueError("Qt border sides require opaque colors.")
        result.append(
            f"border-{side}: {width.value:g}px solid {color.value};"
            if width.value else f"border-{side}: none;"
        )
    return tuple(result)


def native_side_border_paint(
    computed: ComputedStyle | None,
) -> tuple[tuple[str, float, tuple[float, float, float, float]], ...]:
    """Return explicitly authored side strokes for an RGBA-capable native painter.

    Unlike the uniform border, a side-only declaration must not synthesize
    strokes on the other edges. Resolve fallback width/color from CSS's
    computed values, but include only explicitly specified sides.
    """
    from psx.sfle.lengths import Length, LengthKind

    if computed is None:
        return ()
    result = []
    for side in ("top", "right", "bottom", "left"):
        width_key = f"border-{side}-width"
        color_key = f"border-{side}-color"
        if width_key not in computed.specified and color_key not in computed.specified:
            continue
        width = computed.properties[width_key] if width_key in computed.specified else computed.properties["border-width"]
        color = computed.properties[color_key] if color_key in computed.specified else computed.properties["border-color"]
        if not isinstance(width, Length) or width.kind is not LengthKind.PX or width.value < 0:
            raise ValueError("Native CSS side borders require nonnegative pixel widths.")
        if not isinstance(color, CssColor):
            raise TypeError("Native CSS side border needs a validated color.")
        if width.value == 0:
            continue
        raw = color.value.removeprefix("#")
        if len(raw) in (3, 4):
            channels = [int(part * 2, 16) for part in raw]
        else:
            channels = [int(raw[i:i + 2], 16) for i in range(0, len(raw), 2)]
        if len(channels) == 3:
            channels.append(255)
        result.append((side, float(width.value), tuple(c / 255 for c in channels)))
    return tuple(result)


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
    declarations.extend(native_side_border_styles(computed))
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
                declarations.append("font-family: " + ", ".join(
                    name.strip() if name.strip() in ("serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui")
                    else '"' + name.strip() + '"'
                    for name in value.split(",")
                ) + ";")
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

def native_text_typography(computed: ComputedStyle | None, *, alpha: bool = False, line_height: bool = False) -> dict[str, object]:
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
        # Toolkit font setters generally accept one family, not CSS lists.
        # Keep the leading preferred face; the QSS bridge carries the stack.
        result["font-family"] = family.split(",", 1)[0].strip()
    if "font-size" in computed.specified:
        size = computed.properties["font-size"]
        if not isinstance(size, Length) or size.kind is not LengthKind.PX or size.value <= 0:
            raise ValueError("Native Text font-size requires positive px units.")
        result["font-size"] = size.value
    if "font-weight" in computed.specified:
        weight = computed.properties["font-weight"]
        if type(weight) is not int or weight not in range(100, 1000, 100):
            raise ValueError("Portable native Text requires font-weight from 100 to 900 in steps of 100.")
        result["font-weight"] = weight
    if "text-align" in computed.specified:
        alignment = computed.properties["text-align"]
        if alignment not in ("left", "right", "center", "start", "end"):
            raise ValueError("Native Text does not support justify alignment.")
        result["text-align"] = {"start": "left", "end": "right"}.get(alignment, alignment)
    if "line-height" in computed.specified:
        if not line_height:
            raise ValueError("Native Text line-height is not certified by the text metrics bridge.")
        leading = computed.properties["line-height"]
        if not isinstance(leading, Length) or leading.kind is not LengthKind.PX or leading.value <= 0:
            raise ValueError("Native Text line-height requires positive px units.")
        result["line-height"] = leading.value
    return result


def native_border_paint(computed: ComputedStyle | None, *, alpha: bool = False):
    """An explicitly colored positive pixel stroke; no invented native defaults."""
    from psx.sfle.lengths import Length, LengthKind
    if computed is None or "border-color" not in computed.specified:
        return None
    width = computed.properties["border-width"]
    if not isinstance(width, Length) or width.kind != LengthKind.PX or width.value < 0:
        raise ValueError("Native CSS border requires nonnegative px border-width.")
    if width.value == 0:
        return None
    rgba = border_rgba(computed)
    if rgba is None:
        return None
    if not alpha and rgba[3] != 1.0:
        raise ValueError("Native border paint requires opaque colors.")
    color = rgba if alpha else "#" + "".join(f"{round(c * 255):02x}" for c in rgba[:3])
    return (float(width.value), color)


def native_border_radius(computed: ComputedStyle | None) -> float:
    """Bounded single-value CSS radius, in device-independent px."""
    from psx.sfle.lengths import Length, LengthKind
    if computed is None or "border-radius" not in computed.specified:
        return 0.0
    value = computed.properties["border-radius"]
    if not isinstance(value, Length) or value.kind != LengthKind.PX or value.value < 0:
        raise ValueError("Native CSS border-radius requires nonnegative px units.")
    return float(value.value)
