"""Regression tests for JSX-style PSX conditional comparisons."""

from __future__ import annotations

import ast

import pytest

from psx.core.errors import MarkupSyntaxError
from psx.markup.expressive_ast import (
    Compare, ConditionalAnd, ConditionalOr, InterpolatedString, LogicalNot, Ternary,
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

@pytest.mark.parametrize(
    ("expression", "expected_parts"),
    [
        ('f"Count is {count}"', 2),
        ('f"{{value}} = {count}"', 2),
        ('f"{user.name}: {count}"', 3),
        ("f'Count is {count}'", 2),
    ],
)
def test_fstring_interpolation_lowers_to_joined_string(expression, expected_parts):
    node = parse_expressive_expression(expression)
    assert isinstance(node, InterpolatedString)
    assert len(node.parts) == expected_parts
    lowered = lower(node, filename="test.psx")
    assert isinstance(lowered, ast.JoinedStr)
    assert any(isinstance(item, ast.FormattedValue) for item in lowered.values)
    compile(ast.fix_missing_locations(ast.Expression(body=lowered)), "test.psx", "eval")


def test_ternary_with_fstring_in_jsx_button():
    node = parse_expressive_expression(
        '<Flex><Button on_click={increment_count}>'
        '{count >= 10 ? "Count is high!" : f"Count is {count}"}'
        '</Button></Flex>'
    )
    lowered = lower(node, filename="test.psx")
    compile(ast.fix_missing_locations(ast.Expression(body=lowered)), "test.psx", "eval")


@pytest.mark.parametrize(
    "expression",
    ['f"Unterminated {count"', 'f"Empty {}"', 'f"Unmatched }"', 'f"Invalid {count + 1}"'],
)
def test_unsupported_fstring_syntax_has_markup_error(expression):
    with pytest.raises(MarkupSyntaxError):
        parse_expressive_expression(expression)


def test_component_transform_handles_exact_reported_pattern():
    from psx.markup.transform import transform_source

    source = '''
from psx import psx, component, use_state
@component
def view():
    count, set_count = use_state(0)
    def increment_count():
        set_count(count + 1)
    return psx("""
        <Flex direction="column" gap="12" align_items="center">
            <Text>Hello, Velto!</Text>
            <Button on_click={increment_count}>
                {count >= 10 ? "Count is high!" : f"Count is {count}"}
            </Button>
        </Flex>
    """)
'''
    result = transform_source(source, filename="example.py")
    assert result.transformed_calls == 1
    assert "_psx_expr_" in result.source
    compile(result.source, "example.py", "exec")
