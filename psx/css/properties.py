"""Typed, immutable CSS property metadata and declaration validation.

This is a limited internal foundation, not a stylesheet parser or cascade.
Values remain specified (percentages are not resolved during validation).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

from psx.sfle.lengths import Length, LengthKind, parse_length


@dataclass(frozen=True, slots=True)
class CssDiagnostic:
    property_name: str
    code: str
    message: str


class CssValidationError(ValueError):
    def __init__(self, diagnostic: CssDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


@dataclass(frozen=True, slots=True)
class CssProperty:
    name: str
    initial: Length
    inherited: bool
    allows_negative: bool = False
    allows_percent: bool = True
    keywords: frozenset[LengthKind] = frozenset()

    def __post_init__(self) -> None:
        if not self.name or self.name != self.name.lower() or "_" in self.name:
            raise ValueError("CSS property names must be lowercase and hyphenated.")


@dataclass(frozen=True, slots=True)
class CssDeclaration:
    name: str
    value: Length


class CssPropertyRegistry:
    """Immutable per-instance registry; no global mutable property table."""

    def __init__(self, properties: tuple[CssProperty, ...]) -> None:
        indexed: dict[str, CssProperty] = {}
        for prop in properties:
            if prop.name in indexed:
                raise ValueError(f"Duplicate CSS property: {prop.name}")
            indexed[prop.name] = prop
        self._properties: Mapping[str, CssProperty] = MappingProxyType(indexed)

    @property
    def properties(self) -> Mapping[str, CssProperty]:
        return self._properties

    def validate(self, name: str, value: Length | int | float | str) -> CssDeclaration:
        if not isinstance(name, str):
            raise CssValidationError(CssDiagnostic(str(name), "invalid-name", "CSS property name must be a string."))
        prop = self._properties.get(name)
        if prop is None:
            raise CssValidationError(CssDiagnostic(name, "unknown-property", f"Unsupported CSS property: {name!r}."))
        try:
            length = parse_length(value)
        except (TypeError, ValueError) as exc:
            raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS value for {name!r}: {value!r}.")) from exc
        if length.kind == LengthKind.PERCENT and not prop.allows_percent:
            raise CssValidationError(CssDiagnostic(name, "unsupported-unit", f"Percentages are not supported for {name!r}."))
        if length.kind not in (LengthKind.PX, LengthKind.PERCENT) and length.kind not in prop.keywords:
            raise CssValidationError(CssDiagnostic(name, "unsupported-keyword", f"Unsupported CSS keyword for {name!r}: {length.kind.value}."))
        if length.kind in (LengthKind.PX, LengthKind.PERCENT) and length.value is not None and length.value < 0 and not prop.allows_negative:
            raise CssValidationError(CssDiagnostic(name, "negative-value", f"Negative values are not supported for {name!r}."))
        return CssDeclaration(name, length)


def foundation_registry() -> CssPropertyRegistry:
    """Deliberately narrow sizing vocabulary pending cascade and renderer contracts."""
    return CssPropertyRegistry((
        CssProperty("width", Length(LengthKind.AUTO), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT, LengthKind.FIT_CONTENT})),
        CssProperty("height", Length(LengthKind.AUTO), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT, LengthKind.FIT_CONTENT})),
        CssProperty("min-width", Length.px(0), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("min-height", Length.px(0), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("max-width", Length(LengthKind.NONE), False, keywords=frozenset({LengthKind.NONE, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("max-height", Length(LengthKind.NONE), False, keywords=frozenset({LengthKind.NONE, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
    ))
