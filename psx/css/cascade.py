"""Pure CSS selector matching and specified-style cascade.

This resolver deliberately has no VNode/renderer access. It does not mutate
native properties, create CSS Grid contexts or assign geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from psx.sfle.lengths import Length
from .parser import Stylesheet
from .properties import CssDeclaration, CssPropertyRegistry, foundation_registry


@dataclass(frozen=True, slots=True)
class StyleTarget:
    tag: str
    classes: frozenset[str] = frozenset()
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class ComputedStyle:
    """Immutable snapshot with no references to mounted nodes."""
    properties: Mapping[str, Length]

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ComputedStyle) and dict(self.properties) == dict(other.properties)


def resolve_style(
    sheet: Stylesheet,
    target: StyleTarget,
    *,
    inline: tuple[CssDeclaration, ...] = (),
    inherited: ComputedStyle | None = None,
    registry: CssPropertyRegistry | None = None,
) -> ComputedStyle:
    definitions = registry or foundation_registry()
    resolved = {name: prop.initial for name, prop in definitions.properties.items()}
    if inherited is not None:
        for name, prop in definitions.properties.items():
            if prop.inherited and name in inherited.properties:
                resolved[name] = inherited.properties[name]
    matched: list[tuple[tuple[int, int, int], int, int, str, Length]] = []
    for rule in sheet.rules:
        for selector in rule.selectors:
            if selector.matches(target.tag, target.classes, target.node_id):
                for index, (name, value) in enumerate(rule.declarations):
                    if name not in definitions.properties or not isinstance(value, Length):
                        raise ValueError(f"Invalid precompiled declaration: {name!r}")
                    matched.append((selector.specificity, rule.order, index, name, value))
    for _, _, _, name, value in sorted(matched):
        resolved[name] = value
    for declaration in inline:
        validated = definitions.validate(declaration.name, declaration.value)
        resolved[validated.name] = validated.value
    return ComputedStyle(resolved)
