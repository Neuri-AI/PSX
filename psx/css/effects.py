"""Conservative CSS computed-style change effects, independent of native UI.

Unknown properties require a full layout/measurement/paint update.
"""
from __future__ import annotations

from enum import IntFlag, auto

from .cascade import ComputedStyle
from .visual_values import VISUAL_EFFECTS


class StyleEffect(IntFlag):
    NONE = 0
    PAINT = auto()
    MEASUREMENT = auto()
    GEOMETRY = auto()
    INTERACTION = auto()


_GEOMETRY = frozenset({"width", "height", "min-width", "min-height", "max-width", "max-height", "padding", "margin"})
_MEASUREMENT = frozenset({"font-size", "font-family", "font-weight", "line-height"})


def classify_style_change(previous: ComputedStyle, current: ComputedStyle) -> StyleEffect:
    changed = {
        name for name in previous.properties.keys() | current.properties.keys()
        if previous.properties.get(name) != current.properties.get(name)
    }
    result = StyleEffect.NONE
    for name in changed:
        if name in _GEOMETRY:
            result |= StyleEffect.GEOMETRY
        elif name in _MEASUREMENT:
            result |= StyleEffect.MEASUREMENT | StyleEffect.GEOMETRY
        elif name in VISUAL_EFFECTS:
            result |= StyleEffect.PAINT
        else:
            result |= StyleEffect.PAINT | StyleEffect.MEASUREMENT | StyleEffect.GEOMETRY | StyleEffect.INTERACTION
    return result
