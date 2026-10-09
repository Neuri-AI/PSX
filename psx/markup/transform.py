"""M4B static transform for lexical PSX markup.

The transformer never captures frames or evaluates template expressions.  It
generates ordinary Python ``Name`` nodes in the original lexical scope and
hoists each statically known template into a module-level compiled factory.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from psx.core.registry import builtin_component_registry

from .ast import Document, Fragment, Node, Reference, ReferencePart, TextNode
from .parser import parse



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

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not _is_transformable_psx_call(node):
            return node
        source = node.args[0].value
        template_filename = f"{self.filename}:{node.lineno}:{node.col_offset + 1}"
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


def transform_source(source: str, *, filename: str = "<module>") -> TransformResult:
    """Transform statically known inline ``psx`` calls into lexical factories.

    Calls that already supply ``scope=`` and calls whose first argument is not a
    literal string remain untouched and continue using the explicit-scope M4A API.
    """
    module = ast.parse(source, filename=filename)
    transformer = _Transformer(filename)
    module = transformer.visit(module)
    if transformer.templates:
        insertion = _insertion_index(module.body)
        declarations = _factory_declarations(transformer.templates)
        module.body[insertion:insertion] = declarations
    ast.fix_missing_locations(module)
    return TransformResult(
        source=ast.unparse(module) + "\n",
        source_map=SourceMap(filename, tuple(transformer.entries)),
        transformed_calls=len(transformer.templates),
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
    if not builtin_component_registry().contains(node.name):
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
