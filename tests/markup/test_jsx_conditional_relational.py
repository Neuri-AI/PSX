"""Regression tests for JSX-style PSX conditional comparisons."""

from __future__ import annotations

import ast

import pytest

from psx.core.errors import MarkupSyntaxError
from psx.markup.expressive_ast import (
    Compare, ConditionalAnd, ConditionalOr, LogicalNot, Ternary,
    parse_expressive_expression,
)
from psx.markup.expressive_lower import lower


@pytest.mark.parametrize(
    ("expression", "operator", "expected_ast"),
    [
        ("age > 18", ">", ast.Gt),
        ("age < 18", "<", ast.Lt),
        ("age >= 18", ">=", ast.GtE),
        ("age <= 18", "<=", ast.LtE),
        ("age == 18", "==", ast.Eq),
        ("age != 18", "!=", ast.NotEq),
    ],
)
def test_relational_comparisons(expression, operator, expected_ast):
    node = parse_expressive_expression(expression)
    assert isinstance(node, Compare)
    assert node.operator == operator
    lowered = lower(node, filename="test.psx")
    assert isinstance(lowered, ast.Compare)
    assert isinstance(lowered.ops[0], expected_ast)
    compile(ast.fix_missing_locations(ast.Expression(body=lowered)), "test.psx", "eval")


def test_jsx_boolean_precedence():
    node = parse_expressive_expression("age >= 18 || isAdmin && !blocked")
    assert isinstance(node, ConditionalOr)
    assert isinstance(node.right, ConditionalAnd)
    assert isinstance(node.right.right, LogicalNot)


def test_jsx_ternary_and_nested_jsx():
    node = parse_expressive_expression(
        "age >= 18 ? <Text>Adult</Text> : <Text>Minor</Text>"
    )
    assert isinstance(node, Ternary)
    compile(ast.fix_missing_locations(ast.Expression(body=lower(node, filename="test.psx"))), "test.psx", "eval")


@pytest.mark.parametrize("expression", ["age === 18", "age !== 18", "age >=", "age <"])
def test_invalid_relational_syntax_is_rejected(expression):
    with pytest.raises(MarkupSyntaxError):
        parse_expressive_expression(expression)


def test_relational_operator_does_not_consume_jsx_opening():
    node = parse_expressive_expression("age < 18 && <Text>Minor</Text>")
    assert isinstance(node, ConditionalAnd)
    assert isinstance(node.left, Compare)
    assert node.left.operator == "<"
