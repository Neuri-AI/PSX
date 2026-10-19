"""Internal dependency-effect classification for native layout scheduling.

This is a conservative, backend-neutral characterization of existing public
properties, not a CSS property registry and not a public styling API.
Unknown properties must invalidate layout rather than silently skip Cinnamon.
"""
from __future__ import annotations

from enum import Enum
from typing import Mapping


class ChangeEffect(str, Enum):
    PAINT = "paint"
    MEASUREMENT = "measurement"
    GEOMETRY = "geometry"
    STRUCTURE = "structure"
    INTERACTION = "interaction"


# Deliberately small: only these existing properties are certified as
# non-geometric for these component types. Expand solely with native evidence.
_PAINT_ONLY = frozenset({("Text", "color")})
_MEASUREMENT = frozenset({
    ("Text", "value"), ("Text", "font_size"),
    ("Text", "bold"), ("Text", "italic"),
    ("Button", "label"), ("Button", "font_size"),
    ("Image", "source"), ("Image", "width"), ("Image", "height"),
})
_INTERACTION_ONLY = frozenset({
    ("Text", "enabled"),
})
_LAYOUT_ITEM_FIELDS = frozenset({
    "flex_grow", "flex_shrink", "flex_basis", "align_self", "order",
    "layout_width", "layout_height",
    "layout_min_width", "layout_min_height",
    "layout_max_width", "layout_max_height",
    *(f"layout_{kind}_{side}" for kind in ("margin", "padding", "border")
      for side in ("top", "right", "bottom", "left")),
})
_STRUCTURE_FIELDS = frozenset({"key", "ref"})


def classify_change(component: str, property_name: str) -> ChangeEffect:
    """Return the conservative dependency effect of an existing property."""
    if property_name in _STRUCTURE_FIELDS:
        return ChangeEffect.STRUCTURE
    if (component, property_name) in _PAINT_ONLY:
        return ChangeEffect.PAINT
    if (component, property_name) in _MEASUREMENT:
        return ChangeEffect.MEASUREMENT
    if (component, property_name) in _INTERACTION_ONLY:
        return ChangeEffect.INTERACTION
    if property_name in _LAYOUT_ITEM_FIELDS:
        return ChangeEffect.GEOMETRY
    return ChangeEffect.GEOMETRY


def detached_literal(value: object) -> tuple[bool, object]:
    """Keep only scalar/tuple values; do not retain callbacks or native owners."""
    if value is None or type(value) in (str, int, float, bool):
        return True, value
    if type(value) is tuple:
        parts = tuple(detached_literal(part) for part in value)
        return all(ok for ok, _ in parts), tuple(value for _, value in parts)
    return False, None


def partition_dependency_signature(
    nodes: tuple[tuple[str, str, int, Mapping[str, object]], ...],
    constraints: object,
) -> tuple[tuple[object, object], bool]:
    """Produce immutable dependency and paint fingerprints for mounted nodes.

    Unrecognized or nonliteral values *disable* reuse. The caller owns the
    single successful signature and must clear it on teardown/invalidation.
    Node identifiers and handle ids are values, never strong references.
    """
    safe = True
    geometry = []
    paint = []
    for node_id, component, handle_id, props in nodes:
        dependencies = []
        for name, value in sorted(props.items()):
            valid, detached = detached_literal(value)
            safe &= valid
            if classify_change(component, name) is ChangeEffect.PAINT:
                paint.append((node_id, name, detached))
            else:
                # Measurement, geometry, structure and interaction stay in
                # the conservative signature until separately certified.
                dependencies.append((name, detached))
        geometry.append((node_id, component, handle_id, tuple(dependencies)))
    return ((constraints, tuple(geometry)), tuple(paint)), safe
