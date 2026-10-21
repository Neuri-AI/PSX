"""Strict, bounded CSS stylesheet parser with source-order preserving rules.

Subset: type, .class and #id single-compound selectors; plain declarations.
Unsupported at-rules, combinators, functions and important fail closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .properties import CssValidationError, foundation_registry

_IDENT = r"[a-zA-Z_][a-zA-Z0-9_-]*"
_SELECTOR = re.compile(rf"^(?P<tag>{_IDENT})?(?P<qualifiers>(?:[.#]{_IDENT})*)$")
_QUALIFIER = re.compile(rf"([.#])({_IDENT})")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


@dataclass(frozen=True, slots=True)
class Selector:
    tag: str | None
    classes: frozenset[str]
    node_id: str | None

    @property
    def specificity(self) -> tuple[int, int, int]:
        return (int(self.node_id is not None), len(self.classes), int(self.tag is not None and self.tag != "*"))

    def matches(self, tag: str, classes: frozenset[str], node_id: str | None) -> bool:
        return (self.tag is None or self.tag == "*" or self.tag == tag) and self.classes.issubset(classes) and (
            self.node_id is None or self.node_id == node_id
        )


@dataclass(frozen=True, slots=True)
class Rule:
    selectors: tuple[Selector, ...]
    declarations: tuple[tuple[str, object], ...]
    order: int


@dataclass(frozen=True, slots=True)
class Stylesheet:
    rules: tuple[Rule, ...]


class CssSyntaxError(ValueError):
    pass


def parse_selector(source: str) -> Selector:
    text = source.strip()
    if text == "*":
        return Selector("*", frozenset(), None)
    match = _SELECTOR.fullmatch(text)
    if not match or not text:
        raise CssSyntaxError(f"Unsupported CSS selector: {source!r}.")
    rest = match.group("qualifiers")
    classes: set[str] = set()
    node_id: str | None = None
    for symbol, identifier in _QUALIFIER.findall(rest):
        if symbol == "#":
            if node_id is not None:
                raise CssSyntaxError("A selector may contain only one ID.")
            node_id = identifier
        else:
            classes.add(identifier)
    if not match.group("tag") and not rest:
        raise CssSyntaxError("Empty selector.")
    return Selector(match.group("tag"), frozenset(classes), node_id)


def parse_stylesheet(source: str) -> Stylesheet:
    if not isinstance(source, str):
        raise TypeError("Stylesheet source must be text.")
    if len(source) > 262_144:
        raise CssSyntaxError("Stylesheet exceeds the supported size.")
    cleaned = _COMMENT.sub("", source)
    rules: list[Rule] = []
    offset = 0
    registry = foundation_registry()
    while offset < len(cleaned):
        if not cleaned[offset:].strip():
            break
        opening = cleaned.find("{", offset)
        closing = cleaned.find("}", opening + 1)
        if opening < 0 or closing < 0 or "{" in cleaned[opening + 1:closing]:
            raise CssSyntaxError("Unbalanced or nested CSS rule.")
        selector_text = cleaned[offset:opening].strip()
        if not selector_text or selector_text.startswith("@"):
            raise CssSyntaxError("Unsupported CSS at-rule or empty selector.")
        selectors = tuple(parse_selector(piece) for piece in selector_text.split(","))
        declarations: list[tuple[str, object]] = []
        for entry in cleaned[opening + 1:closing].split(";"):
            if not entry.strip():
                continue
            if entry.count(":") != 1:
                raise CssSyntaxError(f"Malformed CSS declaration: {entry!r}.")
            name, value = (part.strip() for part in entry.split(":", 1))
            try:
                declaration = registry.validate(name, value)
            except CssValidationError as exc:
                raise CssSyntaxError(str(exc)) from exc
            declarations.append((declaration.name, declaration.value))
        rules.append(Rule(selectors, tuple(declarations), len(rules)))
        if len(rules) > 2048:
            raise CssSyntaxError("Stylesheet exceeds the supported rule count.")
        offset = closing + 1
    return Stylesheet(tuple(rules))
