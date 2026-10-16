"""Regression coverage for M4B inline complex literal props."""

import ast

import pytest

from psx.core.errors import MarkupSyntaxError
from psx.markup.expressive_ast import parse_expressive_expression
from psx.markup.expressive_lower import lower
from psx.markup.transform import transform_source
from psx.markup.parser import parse


def test_inline_dictionary_list_tuple_and_nested_values():
    source = '<Welcome user={{"name": "User", "age": 30, "tags": ["a", "b"], "position": (10, 20), "nested": {"active": True}}} />'
    tree = parse_expressive_expression(source)
    code = ast.Expression(lower(tree, filename="test.psx"))
    ast.fix_missing_locations(code)
    compile(code, "test.psx", "eval")
    assert isinstance(code.body, ast.Call)
    props = code.body.args[1]
    assert isinstance(props, ast.Dict)
    assert isinstance(props.values[0], ast.Dict)


def test_inline_literals_trigger_static_transform():
    source = 'def render():\n    return psx(\'<Welcome user={{"name": "User", "age": 30}} />\')\n'
    transformed = transform_source(source, filename="demo.py")
    assert transformed.transformed_calls == 1
    assert "_psx_expr_element" in transformed.source
    compile(transformed.source, "demo.py", "exec")


def test_mixed_lexical_dictionary_values():
    tree = parse_expressive_expression('<Welcome user={{"name": name, "age": 30}} />')
    code = ast.Expression(lower(tree, filename="demo.py"))
    ast.fix_missing_locations(code)
    compile(code, "demo.py", "eval")


@pytest.mark.parametrize("source", [
    '<Welcome user={{"name": "User"} />',
    '<Welcome user={{"name" "User"}} />',
    '<Welcome user={[1, 2} />',
    '<Welcome user={{"name": unknown + 1}} />',
])
def test_invalid_inline_literals_fail_with_diagnostics(source):
    with pytest.raises(MarkupSyntaxError):
        parse_expressive_expression(source, filename="broken.psx")


def test_m4a_rejects_inline_dictionary():
    with pytest.raises(MarkupSyntaxError):
        parse('<Welcome user={{"name": "User"}} />', filename="runtime.psx")


def test_braced_scalar_literal_still_rejected():
    with pytest.raises(MarkupSyntaxError):
        parse_expressive_expression('<Flex gap={12} />')


def test_indexed_access_to_list_and_tuple_props():
    source = '<Welcome user={{"interests": ["coding", "music"], "coords": (10, 20)}} />'
    tree = parse_expressive_expression(source)
    assert tree is not None
    for markup in (
        '<Text>{user.interests[0]}</Text>',
        '<Text>{user.coords[1]}</Text>',
        '<Text>{user["interests"][0]}</Text>',
    ):
        parsed = parse_expressive_expression(markup)
        code = ast.Expression(lower(parsed, filename="demo.psx"))
        ast.fix_missing_locations(code)
        compile(code, "demo.psx", "eval")
        transformed = transform_source('def render():\n    return psx(' + repr(markup) + ')\n')
        assert transformed.transformed_calls == 1


def test_index_diagnostics():
    from psx.markup.expressive_runtime import index
    with pytest.raises(MarkupSyntaxError):
        index(["coding"], 5, "demo.psx", 1, 10)
    with pytest.raises(MarkupSyntaxError):
        index(["coding"], "0", "demo.psx", 1, 10)
