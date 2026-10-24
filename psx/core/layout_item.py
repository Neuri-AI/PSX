"""Shared, closed SFLE layout-item metadata for portable and native children.

Widget properties (such as Image.width or Scroll.width) are owned by their
native contracts. Layout dimensions always use the layout_* namespace when
placed on ordinary controls; callers of this module do not rewrite native
properties or perform layout calculations.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from psx.sfle.lengths import LengthKind, parse_length

from .errors import RendererCapabilityError
from .props import FLEX_ITEM_PROPS

_ITEM_ALIGN = frozenset({
    "auto", "stretch", "flex-start", "flex-end", "center", "baseline",
})
_VIEWPORT = frozenset({LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX})
_SIZE = frozenset({
    LengthKind.PX, LengthKind.PERCENT, LengthKind.AUTO,
    LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT,
}) | _VIEWPORT
_MAX_SIZE = (_SIZE - {LengthKind.AUTO}) | {LengthKind.NONE}
_EDGE = frozenset({LengthKind.PX, LengthKind.PERCENT}) | _VIEWPORT
_MARGIN = _EDGE | {LengthKind.AUTO}
_LENGTH_RULES = {
    "flex_basis": _SIZE,
    **{name: _SIZE for name in (
        "layout_width", "layout_height", "layout_min_width", "layout_min_height",
    )},
    **{name: _MAX_SIZE for name in ("layout_max_width", "layout_max_height")},
    **{f"layout_margin_{side}": _MARGIN for side in ("top", "right", "bottom", "left")},
    **{f"layout_padding_{side}": _EDGE for side in ("top", "right", "bottom", "left")},
    **{f"layout_border_{side}": frozenset({LengthKind.PX}) | _VIEWPORT
       for side in ("top", "right", "bottom", "left")},
}


def validate_flex_item_props(
    props: Mapping[str, object], *, owner: str = "Flex item",
) -> None:
    """Reject invalid item metadata consistently on any participant.

    Only names in FLEX_ITEM_PROPS are interpreted here; the component's
    existing native contract independently rejects unknown native names.
    No min/max dimension or intrinsic native-image sizing is synthesized.
    """
    align = props.get("align_self")
    if "align_self" in props and align not in _ITEM_ALIGN:
        raise RendererCapabilityError(f"{owner}.align_self is unsupported: {align!r}.")
    for name in ("flex_grow", "flex_shrink"):
        if name not in props:
            continue
        value = props[name]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise RendererCapabilityError(f"{owner}.{name} must be finite and >= 0.")
    if "order" in props:
        order = props["order"]
        if (type(order) is not int or not -(1 << 31) <= order < (1 << 31)):
            raise RendererCapabilityError(f"{owner}.order must be a signed 32-bit integer.")

    for name, allowed in _LENGTH_RULES.items():
        if name not in props:
            continue
        value = props[name]
        try:
            parsed = parse_length(value)
        except (ValueError, TypeError) as exc:
            raise RendererCapabilityError(
                f"{owner}.{name} must be a supported SFLE length."
            ) from exc
        if parsed.kind not in allowed:
            raise RendererCapabilityError(
                f"{owner}.{name} has unsupported length kind {parsed.kind.value!r}."
            )
        if name.startswith(("layout_padding_", "layout_border_")) or (
            name != "layout_margin_top" and
            name != "layout_margin_right" and
            name != "layout_margin_bottom" and
            name != "layout_margin_left"
        ):
            if parsed.value is not None and parsed.value < 0:
                raise RendererCapabilityError(f"{owner}.{name} cannot be negative.")
