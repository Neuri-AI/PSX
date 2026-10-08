"""Recursive-descent parser for M4A PSX markup."""

from __future__ import annotations

from .ast import Attribute, Document, Element, Fragment, Node, Reference, ReferencePart, Span, TextNode, TextPart
from .lexer import Lexer, Token


class Parser:
    def __init__(self, source: str, *, filename: str) -> None:
        self.source = source
        self.filename = filename
        self.tokens = Lexer(source, filename=filename).tokens()
        self.index = 0

    def parse(self) -> Document:
        children = self._nodes_until(None)
        self._expect("EOF")
        return Document(tuple(children))

    def _nodes_until(self, closing: str | None) -> list[Node]:
        nodes: list[Node] = []
        while True:
            token = self._current()
            if token.kind == "EOF":
                if closing is not None:
                    self._error(f"Expected closing tag </{closing}>", token.span)
                return nodes
            if token.kind == "LT_SLASH":
                self._advance()
                name = self._expect("NAME")
                self._expect("GT")
                if closing is None:
                    self._error(f"Unexpected closing tag </{name.value}>", name.span)
                if name.value != closing:
                    self._error(f"Expected closing tag </{closing}>, got </{name.value}>", name.span)
                return nodes
            if token.kind == "FRAGMENT_CLOSE":
                if closing != "":
                    self._error("Unexpected fragment closing tag", token.span)
                self._advance()
                return nodes
            nodes.append(self._node())

    def _node(self) -> Node:
        token = self._current()
        if token.kind == "TEXT":
            self._advance()
            return TextNode(_text_parts(token.value, token.span, self.filename), token.span)
        if token.kind == "FRAGMENT_OPEN":
            self._advance()
            return Fragment(tuple(self._nodes_until("")), token.span)
        if token.kind == "LT":
            return self._element()
        self._error("Expected element, fragment, or text", token.span)

    def _element(self) -> Element:
        start = self._expect("LT").span
        name = self._expect("NAME")
        attributes: list[Attribute] = []
        while self._current().kind not in {"GT", "SLASH_GT"}:
            attr_name = self._expect("NAME")
            value: str | bool | int | float | Reference = True
            if self._current().kind == "EQUAL":
                self._advance()
                value = self._attribute_value()
            attributes.append(Attribute(attr_name.value, value, attr_name.span))
        end = self._advance()
        if end.kind == "SLASH_GT":
            return Element(name.value, tuple(attributes), (), start)
        return Element(name.value, tuple(attributes), tuple(self._nodes_until(name.value)), start)

    def _attribute_value(self) -> str | int | float | Reference:
        token = self._current()
        if token.kind == "STRING":
            self._advance()
            return token.value
        if token.kind == "LBRACE":
            self._advance()
            value = self._current()
            if value.kind == "NUMBER":
                self._advance()
                self._expect("RBRACE")
                return float(value.value) if "." in value.value else int(value.value)
            name = self._expect("NAME")
            self._expect("RBRACE")
            return _reference(name.value, name.span, self.filename)
        self._error("Expected quoted string, {reference}, or {number} attribute value", token.span)

    def _current(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        current = self._current()
        self.index += 1
        return current

    def _expect(self, kind: str) -> Token:
        token = self._current()
        if token.kind != kind:
            self._error(f"Expected {kind}, got {token.kind}", token.span)
        self.index += 1
        return token

    def _error(self, message: str, span: Span) -> None:
        from psx.core.errors import MarkupSyntaxError

        raise MarkupSyntaxError(message, filename=self.filename, line=span.line, column=span.column)


def parse(source: str, *, filename: str = "<psx>") -> Document:
    return Parser(source, filename=filename).parse()


def _text_parts(value: str, start: Span, filename: str) -> tuple[TextPart | ReferencePart, ...]:
    parts: list[TextPart | ReferencePart] = []
    index = 0
    line, column = start.line, start.column
    literal_start = 0
    while index < len(value):
        char = value[index]
        if char == "{":
            if literal_start < index:
                parts.append(TextPart(value[literal_start:index], Span(start.offset + literal_start, line, column)))
            close = value.find("}", index + 1)
            if close == -1:
                raise _markup_error("Unterminated text interpolation", filename, line, column)
            path = value[index + 1:close]
            ref_span = Span(start.offset + index, line, column)
            parts.append(ReferencePart(_reference(path, ref_span, filename)))
            index = close + 1
            literal_start = index
            continue
        if char == "}":
            raise _markup_error("Unexpected } in text", filename, line, column)
        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1
        index += 1
    if literal_start < len(value):
        parts.append(TextPart(value[literal_start:], Span(start.offset + literal_start, line, column)))
    return tuple(parts)


def _reference(value: str, span: Span, filename: str) -> Reference:
    if not value or any(not part or not part.replace("_", "a").isalnum() or part[0].isdigit() for part in value.split(".")):
        raise _markup_error("References must be identifiers or dotted identifiers", filename, span.line, span.column)
    return Reference(tuple(value.split(".")), span)


def _markup_error(message: str, filename: str, line: int, column: int) -> Exception:
    from psx.core.errors import MarkupSyntaxError

    return MarkupSyntaxError(message, filename=filename, line=line, column=column)
