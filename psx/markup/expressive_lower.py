"""Compile owner-authored expressive syntax trees into ordinary Python AST.

This is an M4B-only static compilation step. Runtime M4A strings cannot enter
this path, and no evaluation API or frame inspection is used.
"""
from __future__ import annotations

import ast

from psx.core.errors import MarkupSyntaxError
from psx.core.registry import builtin_component_registry
from psx.markup.html_aliases import PORTABLE_HTML_ALIASES
from . import expressive_ast as syntax

_BUILTINS = frozenset(builtin_component_registry().snapshot()) | frozenset(PORTABLE_HTML_ALIASES) | {"link"}


def _helper(name: str, *args: ast.expr) -> ast.Call:
    return ast.Call(func=ast.Name(id=f"_psx_expr_{name}", ctx=ast.Load()),
                    args=list(args), keywords=[])


def _loc(node: syntax.Expression, filename: str) -> tuple[ast.Constant, ...]:
    location = node.location
    return (ast.Constant(filename), ast.Constant(location.line),
            ast.Constant(location.column))


def _raise_unsupported(node: syntax.Expression, filename: str, name: str) -> None:
    loc = node.location
    raise MarkupSyntaxError(
        f"{name} is reserved for a later expressive markup gate",
        filename=filename, line=loc.line, column=loc.column,
    )


def lower(node: syntax.Expression, *, filename: str, child: bool = False) -> ast.expr:
    if isinstance(node, syntax.Literal):
        return ast.Constant(value=node.value)
    if isinstance(node, syntax.Collection):
        values = [lower(item, filename=filename) for item in node.items]
        if node.kind == "list":
            return ast.List(elts=values, ctx=ast.Load())
        return ast.Tuple(elts=values, ctx=ast.Load())
    if isinstance(node, syntax.Dictionary):
        return ast.Dict(
            keys=[lower(key, filename=filename) for key, _ in node.entries],
            values=[lower(value, filename=filename) for _, value in node.entries],
        )
    if isinstance(node, syntax.InterpolatedString):
        return ast.JoinedStr(values=[
            ast.Constant(value=part.value) if isinstance(part, syntax.Literal)
            else ast.FormattedValue(value=lower(part, filename=filename), conversion=-1)
            for part in node.parts
        ])
    if isinstance(node, syntax.Name):
        # Author's ordinary Python lexical name remains in its own scope.
        thunk = ast.Lambda(
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[],
                               kw_defaults=[], defaults=[]),
            body=ast.Name(id=node.value, ctx=ast.Load()),
        )
        return _helper("lexical", thunk, ast.Constant(node.value), *_loc(node, filename))
    if isinstance(node, syntax.Member):
        return _helper("member", lower(node.target, filename=filename),
                       ast.Constant(node.name), *_loc(node, filename))
    if isinstance(node, syntax.Index):
        return _helper("index", lower(node.target, filename=filename),
                       lower(node.index, filename=filename), *_loc(node, filename))
    if isinstance(node, syntax.Call):
        return ast.Call(
            func=lower(node.callee, filename=filename),
            args=[lower(arg, filename=filename) for arg in node.arguments],
            keywords=[],
        )
    if isinstance(node, syntax.Binary):
        operators: dict[str, type[ast.operator]] = {
            "+": ast.Add, "-": ast.Sub, "*": ast.Mult, "/": ast.Div,
        }
        return ast.BinOp(left=lower(node.left, filename=filename),
                         op=operators[node.operator](),
                         right=lower(node.right, filename=filename))
    if isinstance(node, syntax.Compare):
        operators: dict[str, type[ast.cmpop]] = {
            "==": ast.Eq, "!=": ast.NotEq,
            ">": ast.Gt, "<": ast.Lt, ">=": ast.GtE, "<=": ast.LtE,
        }
        operator = operators[node.operator]()
        return ast.Compare(
            left=lower(node.left, filename=filename), ops=[operator],
            comparators=[lower(node.right, filename=filename)],
        )
    if isinstance(node, syntax.LogicalNot):
        return ast.UnaryOp(op=ast.Not(), operand=lower(node.operand, filename=filename))
    if isinstance(node, syntax.ConditionalOr):
        branch = ast.BoolOp(
            op=ast.Or(), values=[lower(node.left, filename=filename),
                                   lower(node.right, filename=filename, child=child)],
        )
        return _helper("conditional", branch) if child else branch
    if isinstance(node, syntax.ConditionalAnd):
        branch = ast.IfExp(
            test=lower(node.left, filename=filename),
            body=lower(node.right, filename=filename, child=child),
            orelse=ast.Constant(None),
        )
        return _helper("conditional", branch) if child else branch
    if isinstance(node, syntax.Ternary):
        branch = ast.IfExp(
            test=lower(node.condition, filename=filename),
            body=lower(node.yes, filename=filename, child=child),
            orelse=lower(node.no, filename=filename, child=child),
        )
        return _helper("conditional", branch) if child else branch
    if isinstance(node, syntax.Arrow):
        # Compile callback syntax to a normal lexical Python closure. The
        # body is evaluated only when the caller invokes the function.
        parameters = node.parameters
        return ast.Lambda(
            args=ast.arguments(
                posonlyargs=[], args=[ast.arg(arg=name) for name in parameters],
                kwonlyargs=[], kw_defaults=[], defaults=[],
            ),
            body=lower(node.body, filename=filename),
        )
    if isinstance(node, syntax.Map):
        # Map is compiler syntax, not a Python list method. Its callback is a
        # lexical Python lambda generated at transform time, never evaluated
        # from a string and never shared across iterations.
        parameters = node.callback.parameters
        callback = ast.Lambda(
            args=ast.arguments(posonlyargs=[],
                               args=[ast.arg(arg=name) for name in parameters],
                               kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=lower(node.callback.body, filename=filename, child=True),
        )
        return _helper("map_children",
                       lower(node.iterable, filename=filename),
                       callback, ast.Constant(len(parameters) == 2),
                       *_loc(node, filename))
    if isinstance(node, syntax.Fragment):
        return _helper("fragment", *(lower(part, filename=filename, child=True)
                                     for part in node.children if not _blank(part)))
    if isinstance(node, syntax.Element):
        tag = node.tag
        if tag == "link":
            return ast.Constant(None)
        values: list[ast.expr] = []
        names: list[ast.expr] = []
        for name, value in node.attributes:
            names.append(ast.Constant(name))
            if isinstance(value, syntax.Expression.__args__):
                values.append(lower(value, filename=filename))
            else:
                values.append(ast.Constant(value))
        props = ast.Dict(keys=names, values=values)
        # HTML collapses whitespace between inline siblings to one space.
        # An isolated text literal between two spans is content, not source
        # indentation. Keep it inside mixed inline formatting hosts while
        # still dropping leading/trailing source-only whitespace.
        mixed_inline = (
            tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6",
                    "div", "main", "section", "header", "footer", "li", "label")
            and any(isinstance(part, syntax.Element)
                    and part.tag in ("span", "label")
                    for part in node.children)
        )
        lowered_children = []
        for index, part in enumerate(node.children):
            if _blank(part):
                if mixed_inline and 0 < index < len(node.children) - 1:
                    lowered_children.append(ast.Constant(value=" "))
                continue
            lowered_children.append(lower(part, filename=filename, child=True))
        children = ast.Tuple(elts=lowered_children, ctx=ast.Load())
        custom = (ast.Constant(None) if tag in _BUILTINS
                  else lower(syntax.Name(tag, node.location), filename=filename))
        return _helper("element", ast.Constant(tag), props, children,
                       *_loc(node, filename), custom)
    raise TypeError(f"Unexpected expressive AST node {type(node).__name__}")


def _blank(node: syntax.Expression) -> bool:
    return isinstance(node, syntax.Literal) and isinstance(node.value, str) and not node.value.strip()


def helper_import() -> ast.ImportFrom:
    return ast.ImportFrom(
        module="psx.markup.expressive_runtime",
        names=[
            ast.alias(name="element", asname="_psx_expr_element"),
            ast.alias(name="fragment", asname="_psx_expr_fragment"),
            ast.alias(name="lexical", asname="_psx_expr_lexical"),
            ast.alias(name="member", asname="_psx_expr_member"),
            ast.alias(name="index", asname="_psx_expr_index"),
            ast.alias(name="conditional", asname="_psx_expr_conditional"),
            ast.alias(name="map_children", asname="_psx_expr_map_children"),
            ast.alias(name="compute_expressive_markup_styles", asname="_psx_expr_compute_styles"),
        ],
        level=0,
    )
