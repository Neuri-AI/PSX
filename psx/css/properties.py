"""Typed, immutable CSS property metadata and declaration validation.

This is a limited internal foundation, not a stylesheet parser or cascade.
Values remain specified (percentages are not resolved during validation).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from psx.sfle.lengths import Length, LengthKind, parse_length
from .visual_values import VISUAL_EFFECTS, normalize_visual_value, CssColor


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
    initial: object
    inherited: bool
    effect: str = "geometry"
    grammar: str = "length"
    allows_negative: bool = False
    allows_percent: bool = True
    keywords: frozenset[LengthKind] = frozenset()
    choices: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.name or self.name != self.name.lower() or "_" in self.name:
            raise ValueError("CSS property names must be lowercase and hyphenated.")


@dataclass(frozen=True, slots=True)
class CssDeclaration:
    name: str
    value: object


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
        # CSS background is a shorthand. The certified solid-color subset
        # maps directly to background-color; unsupported images/layers still fail.
        if name == "background":
            name = "background-color"
        prop = self._properties.get(name)
        if prop is None:
            raise CssValidationError(CssDiagnostic(name, "unknown-property", f"Unsupported CSS property: {name!r}."))
        if prop.grammar == "nonnegative-number":
            from math import isfinite
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS number for {name!r}.")) from exc
            if isinstance(value, bool) or not isfinite(number) or number < 0:
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS number for {name!r}."))
            return CssDeclaration(name, number)
        if prop.grammar == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS integer for {name!r}.")) from exc
            if isinstance(value, bool) or str(value).strip() not in (str(number), f"+{number}"):
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS integer for {name!r}."))
            return CssDeclaration(name, number)
        if prop.grammar == "keyword":
            if not isinstance(value, str) or value not in prop.choices:
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Unsupported CSS value for {name!r}: {value!r}."))
            return CssDeclaration(name, value)
        if prop.grammar == "visual":
            try:
                return CssDeclaration(name, normalize_visual_value(name, value))
            except (TypeError, ValueError) as exc:
                raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS value for {name!r}: {value!r}.")) from exc
        try:
            length = parse_length(value)
        except (TypeError, ValueError) as exc:
            raise CssValidationError(CssDiagnostic(name, "invalid-value", f"Invalid CSS value for {name!r}: {value!r}.")) from exc
        if length.kind == LengthKind.PERCENT and not prop.allows_percent:
            raise CssValidationError(CssDiagnostic(name, "unsupported-unit", f"Percentages are not supported for {name!r}."))
        if length.kind not in (LengthKind.PX, LengthKind.PERCENT, LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX) and length.kind not in prop.keywords:
            raise CssValidationError(CssDiagnostic(name, "unsupported-keyword", f"Unsupported CSS keyword for {name!r}: {length.kind.value}."))
        if length.kind in (LengthKind.PX, LengthKind.PERCENT, LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX) and length.value is not None and length.value < 0 and not prop.allows_negative:
            raise CssValidationError(CssDiagnostic(name, "negative-value", f"Negative values are not supported for {name!r}."))
        return CssDeclaration(name, length)


def expand_box_shorthand(
    registry: CssPropertyRegistry, name: str, value: object,
) -> tuple[CssDeclaration, ...]:
    """Expand CSS margin/padding clockwise into validated side declarations."""
    if name not in ("margin", "padding"):
        return (registry.validate(name, value),)
    if not isinstance(value, str):
        return (registry.validate(name, value),)
    parts = value.split()
    if len(parts) == 1:
        declaration = registry.validate(name, parts[0])
        return (declaration,) + tuple(
            registry.validate(f"{name}-{side}", parts[0])
            for side in ("top", "right", "bottom", "left")
        )
    if len(parts) not in (2, 3, 4):
        raise CssValidationError(CssDiagnostic(
            name, "invalid-value", f"Invalid CSS value for {name!r}: {value!r}.",
        ))
    if len(parts) == 2:
        top, right = parts
        clockwise = (top, right, top, right)
    elif len(parts) == 3:
        top, right, bottom = parts
        clockwise = (top, right, bottom, right)
    else:
        clockwise = tuple(parts)
    return tuple(
        registry.validate(f"{name}-{side}", token)
        for side, token in zip(("top", "right", "bottom", "left"), clockwise)
    )


def foundation_registry() -> CssPropertyRegistry:
    """Deliberately narrow sizing vocabulary pending cascade and renderer contracts."""
    return CssPropertyRegistry((
        CssProperty("display", "block", False, grammar="keyword", choices=frozenset({"block", "inline", "flex", "inline-flex"})),
        CssProperty("flex-direction", "row", False, grammar="keyword", choices=frozenset({"row", "column", "row-reverse", "column-reverse"})),
        CssProperty("flex-wrap", "nowrap", False, grammar="keyword", choices=frozenset({"nowrap", "wrap", "wrap-reverse"})),
        CssProperty("justify-content", "flex-start", False, grammar="keyword", choices=frozenset({"flex-start", "flex-end", "center", "space-between", "space-around", "space-evenly"})),
        CssProperty("align-items", "stretch", False, grammar="keyword", choices=frozenset({"stretch", "flex-start", "flex-end", "center"})),
        CssProperty("align-content", "stretch", False, grammar="keyword", choices=frozenset({"stretch", "flex-start", "flex-end", "center", "space-between", "space-around", "space-evenly"})),
        CssProperty("align-self", "auto", False, grammar="keyword", choices=frozenset({"auto", "stretch", "flex-start", "flex-end", "center", "baseline"})),
        CssProperty("flex-grow", 0.0, False, grammar="nonnegative-number"),
        CssProperty("flex-shrink", 1.0, False, grammar="nonnegative-number"),
        CssProperty("flex-basis", Length(LengthKind.AUTO), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("order", 0, False, grammar="integer"),
        CssProperty("width", Length(LengthKind.AUTO), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT, LengthKind.FIT_CONTENT})),
        CssProperty("height", Length(LengthKind.AUTO), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT, LengthKind.FIT_CONTENT})),
        CssProperty("min-width", Length.px(0), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("min-height", Length.px(0), False, keywords=frozenset({LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("max-width", Length(LengthKind.NONE), False, keywords=frozenset({LengthKind.NONE, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("max-height", Length(LengthKind.NONE), False, keywords=frozenset({LengthKind.NONE, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT})),
        CssProperty("margin", Length.px(0), False, allows_negative=True, keywords=frozenset({LengthKind.AUTO})),
        CssProperty("margin-top", Length.px(0), False, allows_negative=True, keywords=frozenset({LengthKind.AUTO})),
        CssProperty("margin-right", Length.px(0), False, allows_negative=True, keywords=frozenset({LengthKind.AUTO})),
        CssProperty("margin-bottom", Length.px(0), False, allows_negative=True, keywords=frozenset({LengthKind.AUTO})),
        CssProperty("margin-left", Length.px(0), False, allows_negative=True, keywords=frozenset({LengthKind.AUTO})),
        CssProperty("padding", Length.px(0), False),
        CssProperty("padding-top", Length.px(0), False),
        CssProperty("padding-right", Length.px(0), False),
        CssProperty("padding-bottom", Length.px(0), False),
        CssProperty("padding-left", Length.px(0), False),
        CssProperty("gap", Length.px(0), False),
        CssProperty("row-gap", Length.px(0), False),
        CssProperty("column-gap", Length.px(0), False),
        CssProperty("border-width", Length.px(0), False),
        CssProperty("border-top-width", Length.px(0), False),
        CssProperty("border-right-width", Length.px(0), False),
        CssProperty("border-bottom-width", Length.px(0), False),
        CssProperty("border-left-width", Length.px(0), False),
        CssProperty("color", CssColor("#000"), True, effect="paint", grammar="visual"),
        CssProperty("background-color", CssColor("#0000"), False, effect="paint", grammar="visual"),
        CssProperty("border-color", CssColor("#000"), False, effect="paint", grammar="visual"),
        CssProperty("border-top-color", CssColor("#000"), False, effect="paint", grammar="visual"),
        CssProperty("border-right-color", CssColor("#000"), False, effect="paint", grammar="visual"),
        CssProperty("border-bottom-color", CssColor("#000"), False, effect="paint", grammar="visual"),
        CssProperty("border-left-color", CssColor("#000"), False, effect="paint", grammar="visual"),
        CssProperty("border-radius", Length.px(0), False, effect="paint", grammar="visual"),
        CssProperty("font-family", "sans-serif", True, effect="measurement", grammar="visual"),
        CssProperty("font-size", Length.px(16), True, effect="measurement", grammar="visual"),
        CssProperty("font-weight", 400, True, effect="measurement", grammar="visual"),
        CssProperty("line-height", Length.px(19.2), True, effect="measurement", grammar="visual"),
        CssProperty("text-align", "start", True, effect="paint", grammar="visual"),
        CssProperty("cursor", "auto", True, effect="paint", grammar="keyword", choices=frozenset({"auto", "default", "none", "context-menu", "help", "pointer", "progress", "wait"})),
    ))
