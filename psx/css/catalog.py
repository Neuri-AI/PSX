"""Versioned internal CSS vocabulary status without expanding public support.

"parsed-internal" means declaration resolution only; it is not a guarantee of
native rendering. Planned entries must fail closed in the active registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .properties import foundation_registry


@dataclass(frozen=True, slots=True)
class CssCapability:
    name: str
    category: str
    status: str
    runtime_target: str


_PLANNED: dict[str, tuple[str, str]] = {
    "box-sizing": ("box-model", "geometry"),
    "display": ("layout", "geometry"),
    "overflow": ("overflow", "native"),
    "overflow-x": ("overflow", "native"),
    "overflow-y": ("overflow", "native"),
    "flex-direction": ("flexbox", "geometry"),
    "flex-grow": ("flexbox", "geometry"),
    "flex-shrink": ("flexbox", "geometry"),
    "flex-basis": ("flexbox", "geometry"),
    "justify-content": ("flexbox", "geometry"),
    "align-items": ("flexbox", "geometry"),
    "align-self": ("flexbox", "geometry"),
    "border-color": ("border", "paint"),
    "border-style": ("border", "paint"),
    "background-image": ("background", "paint"),
    "background-size": ("background", "paint"),
    "background-position": ("background", "paint"),
    "background-repeat": ("background", "paint"),
    "font-style": ("typography", "measurement"),
    "letter-spacing": ("typography", "measurement"),
    "text-decoration": ("typography", "paint"),
    "opacity": ("paint", "paint"),
    "grid-template-columns": ("css-grid", "separate-algorithm"),
    "grid-template-rows": ("css-grid", "separate-algorithm"),
    "position": ("position", "separate-contract"),
    "transform": ("effects", "separate-contract"),
    "transition": ("effects", "separate-contract"),
    "animation": ("effects", "separate-contract"),
}


def _category(name: str) -> str:
    if name.startswith(("font-", "line-", "text-")) or name == "color":
        return "typography"
    if name.startswith("background-"):
        return "background"
    if name.startswith("border-"):
        return "border"
    if name.startswith(("padding", "margin", "gap", "row-gap", "column-gap")):
        return "spacing"
    return "sizing"


def css_capability_catalog() -> Mapping[str, CssCapability]:
    items: dict[str, CssCapability] = {}
    for name, metadata in foundation_registry().properties.items():
        items[name] = CssCapability(name, _category(name), "parsed-internal", metadata.effect)
    for name, (category, target) in _PLANNED.items():
        if name in items:
            raise RuntimeError(f"CSS capability catalog has duplicate {name!r}")
        items[name] = CssCapability(name, category, "planned-not-supported", target)
    return MappingProxyType(items)
