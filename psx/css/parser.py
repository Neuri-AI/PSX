"""Strict, bounded CSS stylesheet parser with source-order preserving rules.

Subset: type, .class and #id single-compound selectors; plain declarations.
Unsupported at-rules, combinators, functions and important fail closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .properties import CssValidationError, foundation_registry, expand_box_shorthand
from psx.sfle.lengths import Length

_IDENT = r"[a-zA-Z_][a-zA-Z0-9_-]*"
_SELECTOR = re.compile(rf"^(?P<tag>{_IDENT})?(?P<qualifiers>(?:[.#]{_IDENT})*)$")
_QUALIFIER = re.compile(rf"([.#])({_IDENT})")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


@dataclass(frozen=True, slots=True)
class Selector:
    tag: str | None
    classes: frozenset[str]
    node_id: str | None
    parent: Selector | None = None
    descendant: bool = False

    @property
    def specificity(self) -> tuple[int, int, int]:
        return tuple(a + b for a, b in zip((int(self.node_id is not None), len(self.classes), int(self.tag is not None and self.tag != "*")), self.parent.specificity if self.parent else (0, 0, 0)))

    def matches(self, tag: str, classes: frozenset[str], node_id: str | None, parent: object = None) -> bool:
        return (self.tag is None or self.tag == "*" or self.tag == tag) and self.classes.issubset(classes) and (
            self.node_id is None or self.node_id == node_id
        ) and (self.parent is None or (parent is not None and (
            self.parent.matches(parent.tag, parent.classes, parent.node_id, parent.parent)
            or (self.descendant and _ancestor_matches(self.parent, parent.parent))
        )))


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


def _ancestor_matches(selector: Selector, ancestor: object) -> bool:
    while ancestor is not None:
        if selector.matches(ancestor.tag, ancestor.classes, ancestor.node_id, ancestor.parent):
            return True
        ancestor = ancestor.parent
    return False


def parse_selector(source: str) -> Selector:
    text = source.strip()
    if '>' not in text and len(text.split()) == 2:
        ancestor, child_text = text.split()
        child = parse_selector(child_text)
        return Selector(child.tag, child.classes, child.node_id,
                        parse_selector(ancestor), True)
    if '>' in text:
        parts = text.split('>')
        if len(parts) != 2 or not all(part.strip() for part in parts):
            raise CssSyntaxError(f"Unsupported CSS selector: {source!r}.")
        child = parse_selector(parts[1])
        parent = parse_selector(parts[0])
        return Selector(child.tag, child.classes, child.node_id, parent)
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
                if name == "flex":
                    grow = registry.validate("flex-grow", value)
                    declarations.extend((
                        (grow.name, grow.value),
                        ("flex-shrink", 1.0),
                        ("flex-basis", Length.percent(0)),
                    ))
                    continue
                if name == "border":
                    tokens = value.split()
                    if len(tokens) != 3 or tokens[1] != "solid":
                        raise CssSyntaxError(f"Unsupported CSS border shorthand: {value!r}.")
                    expanded = (
                        registry.validate("border-width", tokens[0]),
                        registry.validate("border-color", tokens[2]),
                    )
                else:
                    expanded = expand_box_shorthand(registry, name, value)
            except CssValidationError as exc:
                raise CssSyntaxError(str(exc)) from exc
            declarations.extend((item.name, item.value) for item in expanded)
        rules.append(Rule(selectors, tuple(declarations), len(rules)))
        if len(rules) > 2048:
            raise CssSyntaxError("Stylesheet exceeds the supported rule count.")
        offset = closing + 1
    return Stylesheet(tuple(rules))
