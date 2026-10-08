"""A mode-aware lexer for PSX markup; it does not execute template content."""

from __future__ import annotations

from dataclasses import dataclass

from psx.core.errors import MarkupSyntaxError

from .ast import Span


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    span: Span


class Lexer:
    def __init__(self, source: str, *, filename: str) -> None:
        self.source = source
        self.filename = filename
        self.offset = 0
        self.line = 1
        self.column = 1
        self.in_tag = False

    def tokens(self) -> tuple[Token, ...]:
        values: list[Token] = []
        while self.offset < len(self.source):
            values.append(self._next())
        values.append(Token("EOF", "", self._span()))
        return tuple(values)

    def _next(self) -> Token:
        if not self.in_tag:
            return self._outside_tag()
        self._skip_space()
        if self.offset >= len(self.source):
            self._error("Unterminated opening tag")
        span = self._span()
        if self.source.startswith("/>", self.offset):
            self._advance(2)
            self.in_tag = False
            return Token("SLASH_GT", "/>", span)
        char = self.source[self.offset]
        if char == ">":
            self._advance(1)
            self.in_tag = False
            return Token("GT", ">", span)
        if char == "=":
            self._advance(1)
            return Token("EQUAL", "=", span)
        if char == "{":
            self._advance(1)
            return Token("LBRACE", "{", span)
        if char == "}":
            self._advance(1)
            return Token("RBRACE", "}", span)
        if char in ("\"", "'"):
            return self._string()
        if char.isdigit():
            return Token("NUMBER", self._number(), span)
        if _is_name_start(char):
            return Token("NAME", self._name(), span)
        self._error(f"Unexpected character {char!r} in tag")

    def _outside_tag(self) -> Token:
        span = self._span()
        if self.source.startswith("</>", self.offset):
            self._advance(3)
            return Token("FRAGMENT_CLOSE", "</>", span)
        if self.source.startswith("<>", self.offset):
            self._advance(2)
            return Token("FRAGMENT_OPEN", "<>", span)
        if self.source.startswith("</", self.offset):
            self._advance(2)
            self.in_tag = True
            return Token("LT_SLASH", "</", span)
        if self.source[self.offset] == "<":
            self._advance(1)
            self.in_tag = True
            return Token("LT", "<", span)
        start = self.offset
        while self.offset < len(self.source) and self.source[self.offset] != "<":
            self._advance(1)
        return Token("TEXT", self.source[start:self.offset], span)

    def _string(self) -> Token:
        quote = self.source[self.offset]
        span = self._span()
        self._advance(1)
        result: list[str] = []
        while self.offset < len(self.source):
            char = self.source[self.offset]
            if char == quote:
                self._advance(1)
                return Token("STRING", "".join(result), span)
            if char == "\\":
                self._advance(1)
                if self.offset >= len(self.source):
                    self._error("Unterminated escape sequence")
                escaped = self.source[self.offset]
                result.append({"n": "\n", "t": "\t", "\\": "\\", quote: quote}.get(escaped, escaped))
                self._advance(1)
            else:
                result.append(char)
                self._advance(1)
        self._error("Unterminated quoted attribute")

    def _name(self) -> str:
        start = self.offset
        self._advance(1)
        while self.offset < len(self.source) and _is_name_continue(self.source[self.offset]):
            self._advance(1)
        return self.source[start:self.offset]

    def _number(self) -> str:
        start = self.offset
        while self.offset < len(self.source) and self.source[self.offset].isdigit():
            self._advance(1)
        if self.offset < len(self.source) and self.source[self.offset] == ".":
            self._advance(1)
            decimal_start = self.offset
            while self.offset < len(self.source) and self.source[self.offset].isdigit():
                self._advance(1)
            if self.offset == decimal_start:
                self._error("Expected digits after decimal point")
        return self.source[start:self.offset]

    def _skip_space(self) -> None:
        while self.offset < len(self.source) and self.source[self.offset].isspace():
            self._advance(1)

    def _span(self) -> Span:
        return Span(self.offset, self.line, self.column)

    def _advance(self, count: int) -> None:
        for _ in range(count):
            if self.source[self.offset] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.offset += 1

    def _error(self, message: str) -> None:
        span = self._span()
        raise MarkupSyntaxError(message, filename=self.filename, line=span.line, column=span.column)


def _is_name_start(char: str) -> bool:
    return char.isalpha() or char == "_"


def _is_name_continue(char: str) -> bool:
    return char.isalnum() or char in "_.-"
