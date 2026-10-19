"""Classify pure computed-style diffs using the canonical internal registry.

Unrecognized properties fail closed; no native paint/layout bypass is granted.
"""
from __future__ import annotations

from enum import IntFlag, auto

from .cascade import ComputedStyle
from .properties import foundation_registry


class StyleEffect(IntFlag):
    NONE = 0
    PAINT = auto()
    MEASUREMENT = auto()
    GEOMETRY = auto()
    INTERACTION = auto()


def classify_style_change(previous: ComputedStyle, current: ComputedStyle) -> StyleEffect:
    definitions = foundation_registry().properties
    changed = {
        name for name in previous.properties.keys() | current.properties.keys()
        if previous.properties.get(name) != current.properties.get(name)
    }
    effect = StyleEffect.NONE
    for name in changed:
        prop = definitions.get(name)
        if prop is None:
            effect |= StyleEffect.PAINT | StyleEffect.MEASUREMENT | StyleEffect.GEOMETRY | StyleEffect.INTERACTION
        elif prop.effect == "paint":
            effect |= StyleEffect.PAINT
        elif prop.effect == "measurement":
            effect |= StyleEffect.MEASUREMENT | StyleEffect.GEOMETRY
        elif prop.effect == "geometry":
            effect |= StyleEffect.GEOMETRY
        else:
            effect |= StyleEffect.PAINT | StyleEffect.MEASUREMENT | StyleEffect.GEOMETRY | StyleEffect.INTERACTION
    return effect
