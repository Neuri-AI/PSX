"""Pure bridge from resolved CSS dimensions to Cinnamon layout item metadata.

Only non-default geometry declarations are mapped. Native component props are
never modified and the bridge does not perform a native geometry commit.
"""
from __future__ import annotations

from psx.css.cascade import ComputedStyle
from psx.sfle.lengths import Length

_SIZES = {
    "width": "layout_width", "height": "layout_height",
    "min-width": "layout_min_width", "min-height": "layout_min_height",
    "max-width": "layout_max_width", "max-height": "layout_max_height",
}
_SIDES = ("top", "right", "bottom", "left")


def css_layout_overrides(computed: ComputedStyle) -> dict[str, Length]:
    """Project supported CSS lengths without injecting paint into layout."""
    if not isinstance(computed, ComputedStyle):
        raise TypeError("Expected immutable computed CSS.")
    props = computed.properties
    specified = computed.specified
    projected: dict[str, Length] = {}
    for css, target in _SIZES.items():
        value = props[css]
        if css in specified:
            if not isinstance(value, Length):
                raise TypeError(f"CSS geometry must be typed: {css}")
            projected[target] = value
    for css, target_prefix in (
        ("margin", "layout_margin_"),
        ("padding", "layout_padding_"),
    ):
        fallback = props[css]
        for side in _SIDES:
            name = f"{css}-{side}"
            value = props[name]
            if name not in specified:
                value = fallback
            if name in specified or css in specified:
                if not isinstance(value, Length):
                    raise TypeError(f"CSS geometry must be typed: {name}")
                projected[target_prefix + side] = value
    width = props["border-width"]
    if "border-width" in specified:
        if not isinstance(width, Length):
            raise TypeError("CSS border width must be a typed length.")
        for side in _SIDES:
            projected["layout_border_" + side] = width
    return projected
