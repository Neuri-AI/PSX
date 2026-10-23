"""Non-executing expressive markup grammar for statically authored M4B templates.

M4A's restricted parser remains a separate entry point. This module builds a
source-spanned syntax tree only; executable lowering belongs to later gates.
"""

from __future__ import annotations

from dataclasses import dataclass

from psx.core.errors import MarkupSyntaxError


@dataclass(frozen=True, slots=True)
class Location:
    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Literal:
    value: object
    location: Location


@dataclass(frozen=True, slots=True)
class InterpolatedString:
    parts: tuple["Literal | Expression", ...]
    location: Location


@dataclass(frozen=True, slots=True)
class Collection:
    kind: str
    items: tuple["Expression", ...]
    location: Location


@dataclass(frozen=True, slots=True)
class Dictionary:
    entries: tuple[tuple["Expression", "Expression"], ...]
    location: Location


@dataclass(frozen=True, slots=True)
class Name:
    value: str
    location: Location


@dataclass(frozen=True, slots=True)
class Member:
    target: "Expression"
    name: str
    location: Location


@dataclass(frozen=True, slots=True)
class Index:
    target: "Expression"
    index: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class Call:
    callee: "Expression"
    arguments: tuple["Expression", ...]
    location: Location


@dataclass(frozen=True, slots=True)
class Compare:
    left: "Expression"
    operator: str
    right: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class ConditionalAnd:
    left: "Expression"
    right: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class ConditionalOr:
    left: "Expression"
    right: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class LogicalNot:
    operand: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class Ternary:
    condition: "Expression"
    yes: "Expression"
    no: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class Arrow:
    parameters: tuple[str, ...]
    body: "Expression"
    location: Location


@dataclass(frozen=True, slots=True)
class Map:
    iterable: "Expression"
    callback: Arrow
    location: Location


@dataclass(frozen=True, slots=True)
class Element:
    tag: str
    attributes: tuple[tuple[str, str | "Expression" | bool], ...]
    children: tuple["Expression", ...]
    location: Location


@dataclass(frozen=True, slots=True)
class Fragment:
    children: tuple["Expression", ...]
    location: Location


Expression = Literal | InterpolatedString | Collection | Dictionary | Name | Member | Index | Call | Compare | ConditionalAnd | ConditionalOr | LogicalNot | Ternary | Arrow | Map | Element | Fragment


class ExpressiveParser:
    """Recursive descent with explicit precedence and non-evaluating JSX scanner."""

    def __init__(self, source: str, *, filename: str = "<psx>", line: int = 1, column: int = 1):
        self.source = source
        self.filename = filename
        self.line = line
        self.column = column
        self.pos = 0

    def location(self, offset: int | None = None) -> Location:
        offset = self.pos if offset is None else offset
        before = self.source[:offset]
        return Location(offset, self.line + before.count("\n"),
                        (len(before.rsplit("\n", 1)[-1]) + 1) if "\n" in before
                        else self.column + offset)

    def error(self, message: str, offset: int | None = None) -> None:
        loc = self.location(offset)
        raise MarkupSyntaxError(message, filename=self.filename, line=loc.line, column=loc.column)

    def skip(self) -> None:
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            self.pos += 1

    def take(self, value: str) -> bool:
        self.skip()
        if self.source.startswith(value, self.pos):
            self.pos += len(value)
            return True
        return False

    def expect(self, value: str) -> None:
        if not self.take(value):
            self.error(f"Expected {value!r}")

    def identifier(self) -> str:
        self.skip()
        start = self.pos
        if start >= len(self.source) or not (self.source[start].isalpha() or self.source[start] == "_"):
            self.error("Expected identifier")
        self.pos += 1
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self.pos += 1
        return self.source[start:self.pos]

    def parse(self) -> Expression:
        result = self.expression()
        self.skip()
        if self.pos != len(self.source):
            self.error("Unexpected trailing expression syntax")
        return result

    def expression(self) -> Expression:
        # Arrow binds more weakly than the nested expression body.
        self.skip()
        mark = self.pos
        parameters = self._arrow_head()
        if parameters is not None:
            return Arrow(parameters, self.expression(), self.location(mark))
        self.pos = mark
        return self.ternary()

    def _arrow_head(self) -> tuple[str, ...] | None:
        mark = self.pos
        if not self.take("("):
            return None
        try:
            self.skip()
            params = ()
            if not self.take(")"):
                first = self.identifier()
                params = (first,)
                if self.take(","):
                    second = self.identifier()
                    if second == first:
                        self.error("Arrow parameters must have distinct names")
                    params = (first, second)
                self.expect(")")
            if not self.take("=>"):
                self.pos = mark
                return None
            return params
        except MarkupSyntaxError:
            self.pos = mark
            return None

    def ternary(self) -> Expression:
        condition = self.disjunction()
        self.skip()
        if not self.take("?"):
            return condition
        yes = self.expression()
        self.expect(":")
        no = self.expression()
        return Ternary(condition, yes, no, condition.location)

    def disjunction(self) -> Expression:
        left = self.conjunction()
        while self.take("||"):
            right = self.conjunction()
            left = ConditionalOr(left, right, left.location)
        return left

    def conjunction(self) -> Expression:
        left = self.comparison()
        while self.take("&&"):
            right = self.comparison()
            left = ConditionalAnd(left, right, left.location)
        return left

    def comparison(self) -> Expression:
        left = self.unary()
        self.skip()
        if self.source.startswith(("===", "!=="), self.pos):
            self.error("Use == or !=, not JavaScript strict equality")
        for operator in ("==", "!=", ">=", "<=", ">", "<"):
            if self.take(operator):
                return Compare(left, operator, self.unary(), left.location)
        return left

    def unary(self) -> Expression:
        self.skip()
        start = self.pos
        if self.source.startswith("!", self.pos) and not self.source.startswith("!=", self.pos):
            self.pos += 1
            return LogicalNot(self.unary(), self.location(start))
        return self.primary()

    def primary(self) -> Expression:
        self.skip()
        start = self.pos
        if self.take("{"):
            entries: list[tuple[Expression, Expression]] = []
            if not self.take("}"):
                while True:
                    key = self.expression()
                    self.expect(":")
                    value = self.expression()
                    entries.append((key, value))
                    if self.take("}"):
                        break
                    self.expect(",")
                    if self.take("}"):
                        break
            return Dictionary(tuple(entries), self.location(start))
        if self.take("["):
            items: list[Expression] = []
            if not self.take("]"):
                while True:
                    items.append(self.expression())
                    if self.take("]"):
                        break
                    self.expect(",")
                    if self.take("]"):
                        break
            return Collection("list", tuple(items), self.location(start))
        if self.take("("):
            result = self.expression()
            if self.take(","):
                items = [result]
                while not self.take(")"):
                    items.append(self.expression())
                    if self.take(")"):
                        break
                    self.expect(",")
                return Collection("tuple", tuple(items), self.location(start))
            self.expect(")")
            return self._postfix(result)
        if self.source.startswith("<", self.pos):
            return self.jsx()
        if self.source.startswith(("f\"", "f'", "F\"", "F'"), self.pos):
            return self._fstring()
        if self.source.startswith(('"', "'"), self.pos):
            return self._string()
        if self.pos < len(self.source) and self.source[self.pos].isdigit():
            while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
                self.pos += 1
            raw = self.source[start:self.pos]
            try:
                value = float(raw) if '.' in raw else int(raw)
            except ValueError:
                self.error("Invalid numeric expression literal", start)
            return Literal(value, self.location(start))
        name = self.identifier()
        if name in ("True", "False", "None"):
            return Literal({"True": True, "False": False, "None": None}[name], self.location(start))
        if name in ("async", "new", "undefined", "this"):
            self.error(f"Unsupported JavaScript keyword {name!r}", start)
        return self._postfix(Name(name, self.location(start)))

    def _postfix(self, value: Expression) -> Expression:
        while True:
            self.skip()
            start = self.pos
            if self.take("."):
                name = self.identifier()
                if name == "map" and self.take("("):
                    callback = self.expression()
                    if not isinstance(callback, Arrow) or len(callback.parameters) not in (1, 2):
                        self.error(".map() requires an arrow callback with item and optional index", start)
                    self.expect(")")
                    if isinstance(callback.body, Element) and not any(
                        name == "key" for name, _ in callback.body.attributes
                    ):
                        self.error("Mapped JSX elements require an explicit stable key", start)
                    value = Map(value, callback, value.location)
                else:
                    value = Member(value, name, value.location)
            elif self.take("["):
                index = self.expression()
                self.expect("]")
                value = Index(value, index, self.location(start))
            elif self.take("("):
                args: list[Expression] = []
                if not self.take(")"):
                    args.append(self.expression())
                    while self.take(","):
                        args.append(self.expression())
                    self.expect(")")
                value = Call(value, tuple(args), value.location)
            else:
                return value

    def _string(self) -> Literal:
        start = self.pos
        quote = self.source[self.pos]
        self.pos += 1
        chars: list[str] = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", quote: quote}
        while self.pos < len(self.source):
            char = self.source[self.pos]
            self.pos += 1
            if char == quote:
                return Literal("".join(chars), self.location(start))
            if char == "\\":
                if self.pos >= len(self.source):
                    self.error("Unterminated string escape", start)
                escaped = self.source[self.pos]
                self.pos += 1
                if escaped not in escapes:
                    self.error("Unsupported string escape sequence", self.pos - 2)
                chars.append(escapes[escaped])
            else:
                if char == "\n":
                    self.error("Unescaped newline in string literal", self.pos - 1)
                chars.append(char)
        self.error("Unterminated quoted string", start)

    def _fstring(self) -> InterpolatedString:
        """Parse Python-like f-strings as bounded PSX expressions, never Python source."""
        start = self.pos
        quote = self.source[self.pos + 1]
        self.pos += 2
        parts: list[Literal | Expression] = []
        chars: list[str] = []
        escapes = {"n": "\\n", "r": "\\r", "t": "\\t", "\\\\": "\\\\", quote: quote}

        def flush() -> None:
            if chars:
                parts.append(Literal("".join(chars), self.location(start)))
                chars.clear()

        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == quote:
                self.pos += 1
                flush()
                return InterpolatedString(tuple(parts), self.location(start))
            if char == "\\\\":
                self.pos += 1
                if self.pos >= len(self.source):
                    self.error("Unterminated f-string escape", start)
                escaped = self.source[self.pos]
                if escaped not in escapes:
                    self.error("Unsupported f-string escape", self.pos - 1)
                chars.append(escapes[escaped])
                self.pos += 1
                continue
            if self.source.startswith("{{", self.pos):
                chars.append("{")
                self.pos += 2
                continue
            if self.source.startswith("}}", self.pos):
                chars.append("}")
                self.pos += 2
                continue
            if char == "{":
                flush()
                self.pos += 1
                self.skip()
                if self.source.startswith("}", self.pos):
                    self.error("Empty f-string interpolation")
                value = self.expression()
                self.expect("}")
                parts.append(value)
                continue
            if char == "}":
                self.error("Unmatched '}' in f-string")
            if char == "\\n":
                self.error("Unescaped newline in f-string", self.pos)
            chars.append(char)
            self.pos += 1
        self.error("Unterminated f-string", start)

    def _quoted_attribute(self, name: str) -> str | InterpolatedString:
        """Bind lexical placeholders in quoted style/class strings at compile time."""
        start = self.pos
        literal = self._string().value
        if name not in ("style", "class", "class_name"):
            return literal
        import re
        # Support both ${name} and {name} in CSS/class values. Other attributes
        # preserve their quoted literal contract.
        pattern = re.compile(r"\$?\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*)\}")
        matches = tuple(pattern.finditer(literal))
        if not matches:
            return literal
        parts: list[Literal | Expression] = []
        cursor = 0
        for match in matches:
            if match.start() > cursor:
                parts.append(Literal(literal[cursor:match.start()], self.location(start)))
            loc = self.location(start + match.start() + 1)
            parts.append(parse_expressive_expression(
                match.group(1), filename=self.filename, line=loc.line,
                column=loc.column + (3 if match.group().startswith("$") else 2),
            ))
            cursor = match.end()
        if cursor < len(literal):
            parts.append(Literal(literal[cursor:], self.location(start)))
        return InterpolatedString(tuple(parts), self.location(start))

    def jsx(self) -> Expression:
        self.skip()
        start = self.pos
        self.expect("<")
        if self.take(">"):
            children = self._jsx_children("")
            return Fragment(tuple(children), self.location(start))
        tag = self.identifier()
        attributes: list[tuple[str, str | Expression | bool]] = []
        while True:
            self.skip()
            if self.take("/>"):
                return Element(tag, tuple(attributes), (), self.location(start))
            if self.take(">"):
                return Element(tag, tuple(attributes), tuple(self._jsx_children(tag)), self.location(start))
            name = self.identifier()
            if self.take("="):
                self.skip()
                if self.source.startswith(('"', "'"), self.pos):
                    value: str | Expression | bool = self._quoted_attribute(name)
                elif self.take("{"):
                    value = self.expression()
                    if isinstance(value, Literal):
                        self.error(
                            "Literal JSX attributes must be quoted; braces are reserved for references and expressions"
                        )
                    self.expect("}")
                else:
                    self.error("JSX attributes require quoted literals or {expressions}")
            else:
                value = True
            if any(existing == name for existing, _ in attributes):
                self.error(f"Duplicate JSX attribute {name!r}")
            attributes.append((name, value))

    def _jsx_children(self, closing: str) -> list[Expression]:
        children: list[Expression] = []
        while self.pos < len(self.source):
            if self.source.startswith("</", self.pos):
                self.pos += 2
                if closing:
                    found = self.identifier()
                    if found != closing:
                        self.error(f"Expected closing tag </{closing}>, got </{found}>")
                self.expect(">")
                return children
            if self.source.startswith("<", self.pos):
                children.append(self.jsx())
            elif self.source.startswith("{", self.pos):
                self.pos += 1
                children.append(self.expression())
                self.expect("}")
            else:
                begin = self.pos
                while self.pos < len(self.source) and self.source[self.pos] not in "<{":
                    self.pos += 1
                if self.pos > begin:
                    children.append(Literal(self.source[begin:self.pos], self.location(begin)))
        self.error(f"Missing closing JSX tag for {closing or 'fragment'}")


def parse_expressive_expression(source: str, *, filename: str = "<psx>",
                                line: int = 1, column: int = 1) -> Expression:
    """Return syntax tree with source positions; never evaluate or lower it."""
    return ExpressiveParser(source, filename=filename, line=line, column=column).parse()
