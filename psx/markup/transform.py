"""M4B static transform for lexical PSX markup.

The transformer never captures frames or evaluates template expressions.  It
generates ordinary Python ``Name`` nodes in the original lexical scope and
hoists each statically known template into a module-level compiled factory.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import Iterable

from psx.core.registry import builtin_component_registry
from psx.markup.html_aliases import PORTABLE_HTML_ALIASES

from .ast import Document, Fragment, Node, Reference, ReferencePart, TextNode
from .parser import parse
from .expressive_ast import parse_expressive_expression, Name as ExpressiveName
from .expressive_lower import helper_import, lower



@dataclass(frozen=True, slots=True)
class SourceMapEntry:
    template_name: str
    python_line: int
    python_column: int
    markup_references: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class SourceMap:
    source_filename: str
    entries: tuple[SourceMapEntry, ...]

    def as_dict(self) -> dict[str, object]:
        return {"source_filename": self.source_filename, "entries": [asdict(item) for item in self.entries]}


@dataclass(frozen=True, slots=True)
class TransformResult:
    source: str
    source_map: SourceMap
    transformed_calls: int


@dataclass(frozen=True, slots=True)
class _Template:
    name: str
    source: str
    filename: str
    identifiers: tuple[str, ...]


class _Transformer(ast.NodeTransformer):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.templates: list[_Template] = []
        self.entries: list[SourceMapEntry] = []
        self.expressive_count = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not _is_transformable_psx_call(node):
            return node
        source = node.args[0].value
        template_filename = f"{self.filename}:{node.lineno}:{node.col_offset + 1}"
        # Only statically authored M4B source may use expressive JSX operators.
        # Dynamic and explicitly scoped M4A calls remain on the old safe path.
        if _has_expressive_interpolation(source):
            tree = parse_expressive_expression(source, filename=template_filename)
            replacement = lower(tree, filename=template_filename)
            links = _expressive_css_links(tree)
            # Global application CSS may contain type selectors even when
            # expressive markup has no class/style attributes.
            replacement = ast.Call(
                func=ast.Attribute(value=ast.Name(id="_psx_expr_element", ctx=ast.Load()), attr="compute_styles", ctx=ast.Load()),
                args=[replacement, ast.Tuple(elts=[ast.Constant(name) for name in links], ctx=ast.Load())],
                keywords=[],
            )
            self.expressive_count += 1
            self.entries.append(SourceMapEntry(
                template_name=f"_psx_expressive_{self.expressive_count - 1}",
                python_line=node.lineno, python_column=node.col_offset + 1,
                markup_references=tuple(_expressive_reference_locations(tree)),
            ))
            return ast.copy_location(replacement, node)
        document = parse(source, filename=template_filename)
        identifiers = _required_identifiers(document)
        # A single leading underscore avoids Python class-body name mangling
        # when an inline template occurs inside an instance method.
        template_name = f"_psx_template_{len(self.templates)}"
        self.templates.append(_Template(template_name, source, template_filename, identifiers))
        self.entries.append(
            SourceMapEntry(
                template_name=template_name,
                python_line=node.lineno,
                python_column=node.col_offset + 1,
                markup_references=tuple(_reference_locations(document)),
            )
        )
        scope = ast.Dict(
            keys=[ast.Constant(name) for name in identifiers],
            values=[
                ast.Lambda(
                    args=ast.arguments(
                        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
                    ),
                    body=ast.Name(id=name, ctx=ast.Load()),
                )
                for name in identifiers
            ],
        )
        replacement = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=template_name, ctx=ast.Load()), attr="render_lexical", ctx=ast.Load()
            ),
            args=[scope],
            keywords=[],
        )
        return ast.copy_location(replacement, node)


def _expressive_reference_locations(node: object) -> Iterable[tuple[int, int]]:
    """Retain original source positions for every lexical name in the AST."""
    if isinstance(node, ExpressiveName):
        yield (node.location.line, node.location.column)
    if is_dataclass(node):
        for field in fields(node):
            if field.name != "location":
                yield from _expressive_reference_locations(getattr(node, field.name))
    elif isinstance(node, (tuple, list)):
        for child in node:
            yield from _expressive_reference_locations(child)


def _has_expressive_interpolation(source: str) -> bool:
    """Find expressive operators in markup expressions, not quoted literals.

    Only expression braces activate G2/G3. Text and quoted attributes containing
    question marks or ampersands keep their existing M4B template behavior.
    """
    # Composite inline attribute literals require the expressive M4B path.
    # The restricted M4A runtime never enters this transform.
    # Native needs the CSS-aware VNode path even without an arrow expression.
    import re
    if re.search(r"<Native(?=[\s/>])", source):
        return True
    if "={{" in source or "={[" in source or "={(" in source:
        return True
    # Quoted attribute interpolation is lexical expressive syntax as well,
    # even without an arrow or conditional expression elsewhere in the tree.
    if "${" in source:
        return True
    # Legacy brace interpolation is enabled only for CSS/class attributes.
    # Preserve quoted literals in all unrelated attributes.
    import re
    if re.search(r'(?:style|class|class_name)\s*=\s*["\'][^"\']*\{[A-Za-z_][A-Za-z0-9_.\[\]]*\}[^"\']*["\']', source):
        return True
    depth = 0
    quoted: str | None = None
    index = 0
    while index < len(source):
        ch = source[index]
        if quoted is not None:
            if ch == "\\":
                index += 2
                continue
            if ch == quoted:
                quoted = None
            index += 1
            continue
        # Quotes only delimit literals *inside* a braced expression.  In markup
        # text an apostrophe (for example, ``you're``) is ordinary content and
        # must not make the scanner ignore a later ``{visible && <Text />}``.
        if depth and ch in ("'", '"'):
            quoted = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(depth - 1, 0)
        elif depth and (source.startswith(('f"', "f'", 'F"', "F'"), index) or source.startswith("&&", index) or source.startswith("||", index) or ch == "?" or ch == "[" or source.startswith(".map(", index) or source.startswith("=>", index)):
            return True
        index += 1
    return False


def transform_source(
    source: str, *, filename: str = "<module>", precompiled: bool = False,
) -> TransformResult:
    """Transform statically known inline ``psx`` calls into lexical factories.

    Calls that already supply ``scope=`` and calls whose first argument is not a
    literal string remain untouched and continue using the explicit-scope M4A API.
    """
    module = ast.parse(source, filename=filename)
    transformer = _Transformer(filename)
    module = transformer.visit(module)
    if transformer.templates or transformer.expressive_count or precompiled:
        insertion = _insertion_index(module.body)
        declarations = ([] if not transformer.expressive_count else [helper_import()])
        declarations.extend(_factory_declarations(transformer.templates) if transformer.templates else [])
        # A frozen module has already passed through this lexical transform.
        # @component must never try to recover its original .py with inspect.
        if precompiled:
            declarations.insert(0, ast.Assign(
                targets=[ast.Name(id="__psx_build_precompiled__", ctx=ast.Store())],
                value=ast.Constant(value=True),
            ))
        module.body[insertion:insertion] = declarations
    ast.fix_missing_locations(module)
    return TransformResult(
        source=ast.unparse(module) + "\n",
        source_map=SourceMap(filename, tuple(transformer.entries)),
        transformed_calls=len(transformer.templates) + transformer.expressive_count,
    )


def transform_file(source_path: Path, output_path: Path, *, map_path: Path | None = None) -> TransformResult:
    """Transform one source file and emit a JSON source-map sidecar when requested."""
    result = transform_source(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.source, encoding="utf-8")
    if map_path is not None:
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(result.source_map.as_dict(), indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile inline PSX markup into lexical Python factories.")
    parser.add_argument("source", type=Path, help="Python source file to transform")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Transformed Python output")
    parser.add_argument("--source-map", type=Path, help="Optional JSON source-map output")
    args = parser.parse_args(argv)
    transform_file(args.source, args.output, map_path=args.source_map)
    return 0


def _is_transformable_psx_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Name)
        and node.func.id == "psx"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and not any(keyword.arg == "scope" for keyword in node.keywords)
    )


def _insertion_index(body: list[ast.stmt]) -> int:
    index = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        index = 1
    while index < len(body):
        statement = body[index]
        if isinstance(statement, ast.ImportFrom) and statement.module == "__future__":
            index += 1
        else:
            break
    return index


def _factory_declarations(templates: Iterable[_Template]) -> list[ast.stmt]:
    imported = ast.ImportFrom(
        module="psx.markup",
        names=[ast.alias(name="compile_template", asname="_psx_compile_template")],
        level=0,
    )
    declarations: list[ast.stmt] = [imported]
    for template in templates:
        declarations.append(
            ast.Assign(
                targets=[ast.Name(id=template.name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_psx_compile_template", ctx=ast.Load()),
                    args=[ast.Constant(template.source)],
                    keywords=[ast.keyword(arg="filename", value=ast.Constant(template.filename))],
                ),
            )
        )
    return declarations


def _required_identifiers(document: Document) -> tuple[str, ...]:
    names: set[str] = set()
    for node in document.children:
        _collect_node_identifiers(node, names)
    return tuple(sorted(names))


def _collect_node_identifiers(node: Node, names: set[str]) -> None:
    if isinstance(node, TextNode):
        for part in node.parts:
            if isinstance(part, ReferencePart):
                names.add(part.reference.path[0])
        return
    if isinstance(node, Fragment):
        for child in node.children:
            _collect_node_identifiers(child, names)
        return
    if node.name not in PORTABLE_HTML_ALIASES and not builtin_component_registry().contains(node.name):
        names.add(node.name)
    for attribute in node.attributes:
        if isinstance(attribute.value, Reference):
            names.add(attribute.value.path[0])
    for child in node.children:
        _collect_node_identifiers(child, names)


def _reference_locations(document: Document) -> Iterable[tuple[int, int]]:
    for node in document.children:
        yield from _node_reference_locations(node)


def _node_reference_locations(node: Node) -> Iterable[tuple[int, int]]:
    if isinstance(node, TextNode):
        for part in node.parts:
            if isinstance(part, ReferencePart):
                yield (part.reference.span.line, part.reference.span.column)
        return
    if isinstance(node, Fragment):
        for child in node.children:
            yield from _node_reference_locations(child)
        return
    for attribute in node.attributes:
        if isinstance(attribute.value, Reference):
            yield (attribute.value.span.line, attribute.value.span.column)
    for child in node.children:
        yield from _node_reference_locations(child)


if __name__ == "__main__":
    raise SystemExit(main())

def _expressive_css_links(node: object) -> tuple[str, ...]:
    """Collect only statically declared local CSS links in expressive markup."""
    from psx.core.errors import MarkupSyntaxError
    from .expressive_ast import Element as ExpressiveElement, Literal
    found: list[str] = []
    def visit(value: object) -> None:
        if isinstance(value, ExpressiveElement) and value.tag == "link":
            attrs = dict(value.attributes)
            rel = attrs.get("rel")
            href = attrs.get("href")
            if (
                set(attrs) != {"rel", "href"}
                or not isinstance(rel, str) or rel != "stylesheet"
                or not isinstance(href, str) or not href.endswith(".css")
                or value.children
            ):
                raise MarkupSyntaxError(
                    'link requires rel="stylesheet" and a literal local CSS href',
                    filename="<psx>", line=value.location.line, column=value.location.column,
                )
            found.append(href)
            return
        if is_dataclass(value):
            for field in fields(value):
                if field.name != "location":
                    visit(getattr(value, field.name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
    visit(node)
    return tuple(found)
