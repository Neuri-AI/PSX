"""Source-spanned AST nodes for the safe M4A markup subset."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Span:
    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Reference:
    path: tuple[str, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class TextPart:
    value: str
    span: Span


@dataclass(frozen=True, slots=True)
class ReferencePart:
    reference: Reference


TextSegment = TextPart | ReferencePart
AttributeValue = str | bool | int | float | Reference


@dataclass(frozen=True, slots=True)
class Attribute:
    name: str
    value: AttributeValue
    span: Span


@dataclass(frozen=True, slots=True)
class TextNode:
    parts: tuple[TextSegment, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class Element:
    name: str
    attributes: tuple[Attribute, ...]
    children: tuple[Node, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class Fragment:
    children: tuple[Node, ...]
    span: Span


Node = Element | Fragment | TextNode


@dataclass(frozen=True, slots=True)
class Document:
    children: tuple[Node, ...]
