"""Source-spanned, non-executing lexical preflight for authored M4B expressions.

This module deliberately does not compile or evaluate expressions. F5-G1 defines
the token/diagnostic boundary; subsequent gates own VNode and Python AST output.
M4A's untrusted explicit-scope parser must never import this preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from psx.core.errors import MarkupSyntaxError


class ExpressiveOperator(str, Enum):
    AND = "&&"
    TERNARY = "?"
    BRANCH = ":"
    ARROW = "=>"
    EQUAL = "=="
    NOT_EQUAL = "!="
    MAP = ".map("


@dataclass(frozen=True, slots=True)
class ExpressionToken:
    operator: ExpressiveOperator
    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class ExpressionInspection:
    source: str
    tokens: tuple[ExpressionToken, ...]


def inspect_expressive_expression(
    source: str, *, filename: str = "<psx>", line: int = 1, column: int = 1
) -> ExpressionInspection:
    """Inspect authored syntax without running code or changing M4A semantics.

    Quotes and escapes protect operator-looking text. Parentheses/brackets and
    expression braces must be balanced. The returned token locations refer to
    the original markup input; lowering is the responsibility of later gates.
    """
    tokens: list[ExpressionToken] = []
    stack: list[tuple[str, int]] = []
    quote: str | None = None
    index = 0

    def position(offset: int) -> tuple[int, int]:
        prefix = source[:offset]
        return line + prefix.count("\n"), (
            (column + offset) if "\n" not in prefix else
            len(prefix.rsplit("\n", 1)[-1]) + 1
        )

    def fail(message: str, offset: int) -> None:
        at_line, at_column = position(offset)
        raise MarkupSyntaxError(message, filename=filename, line=at_line,
                                column=at_column)

    operators = (
        ("===", None), ("!==", None), ("&&", ExpressiveOperator.AND),
        ("=>", ExpressiveOperator.ARROW), ("==", ExpressiveOperator.EQUAL),
        ("!=", ExpressiveOperator.NOT_EQUAL), (".map(", ExpressiveOperator.MAP),
        ("?", ExpressiveOperator.TERNARY), (":", ExpressiveOperator.BRANCH),
    )
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if source.startswith("{#if", index) or source.startswith("{#each", index):
            fail("Markup control directives are unsupported; use M4B expressions", index)
        if source.startswith("async ", index) and "=>" in source[index:]:
            fail("Async arrow functions are not supported", index)
        matching = next(((literal, op) for literal, op in operators
                         if source.startswith(literal, index)), None)
        if matching is not None:
            literal, operator = matching
            if operator is None:
                fail("Use Python == or !=, not JavaScript strict equality", index)
            at_line, at_column = position(index)
            tokens.append(ExpressionToken(operator, index, at_line, at_column))
            if literal == ".map(":
                stack.append(("(", index + 4))
            index += len(literal)
            continue
        if char in "([{":
            stack.append((char, index))
        elif char in ")]}":
            if not stack or "([{".index(stack[-1][0]) != ")]}".index(char):
                fail("Unmatched closing expression delimiter", index)
            stack.pop()
        index += 1
    if quote:
        fail("Unterminated string literal in expressive expression", len(source))
    if stack:
        fail("Unclosed expression delimiter", stack[-1][1])
    return ExpressionInspection(source, tuple(tokens))
