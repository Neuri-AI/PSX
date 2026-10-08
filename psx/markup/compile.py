"""Safe M4A AST compiler: explicit scope, no eval/exec/frame inspection."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from psx.core.component import ComponentType
from psx.core.errors import MarkupSyntaxError
from psx.core.hooks import Ref
from psx.core.native import Native
from psx.core.vnode import Button, Column, Fragment as VFragment, Row, Text, VNode, create_element

from .ast import AttributeValue, Document, Element, Fragment, Node, Reference, ReferencePart, TextNode, TextPart
from .parser import parse

Primitive: TypeAlias = Callable[..., VNode] | ComponentType
_GRAMMAR_VERSION = "m4a-1"
_CACHE_LIMIT = 128
_CACHE: "OrderedDict[tuple[str, str, str, int], CompiledTemplate]" = OrderedDict()
_PRIMITIVES: Mapping[str, Primitive] = {
    "Column": Column,
    "Row": Row,
    "Text": Text,
    "Button": Button,
    "Fragment": VFragment,
    "Native": Native,
}


@dataclass(frozen=True, slots=True)
class CompiledTemplate:
    document: Document
    filename: str
    primitives: Mapping[str, Primitive]

    def render(self, scope: Mapping[str, object] | None = None) -> VNode:
        values = {} if scope is None else scope
        children = _nodes(self.document.children, values, self.primitives, self.filename, lexical=False)
        if len(children) == 1:
            return children[0]
        return VFragment(*children)

    def render_lexical(self, scope: Mapping[str, object]) -> VNode:
        """Render M4B static lexical scope without evaluating template expressions.

        Values are generated source-transform thunks for lexical root names. The
        only dynamic traversal performed here is a parser-validated dotted
        attribute/mapping path; callables obtained along a path are returned,
        never invoked.
        """
        children = _nodes(self.document.children, scope, self.primitives, self.filename, lexical=True)
        if len(children) == 1:
            return children[0]
        return VFragment(*children)


def compile_template(
    source: str, *, filename: str = "<psx>", primitives: Mapping[str, Primitive] | None = None
) -> CompiledTemplate:
    registry = _PRIMITIVES if primitives is None else primitives
    key = (source, filename, _GRAMMAR_VERSION, id(registry))
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached
    compiled = CompiledTemplate(parse(source, filename=filename), filename, registry)
    _CACHE[key] = compiled
    if len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)
    return compiled


def psx(
    source: str,
    *,
    scope: Mapping[str, object] | None = None,
    filename: str = "<psx>",
    primitives: Mapping[str, Primitive] | None = None,
) -> VNode:
    """Compile and render an explicit-scope PSX template into ordinary VNodes."""
    return compile_template(source, filename=filename, primitives=primitives).render(scope)


def clear_template_cache() -> None:
    _CACHE.clear()


def _nodes(
    nodes: tuple[Node, ...],
    scope: Mapping[str, object],
    primitives: Mapping[str, Primitive],
    filename: str,
    *,
    lexical: bool,
) -> list[VNode]:
    result: list[VNode] = []
    for node in nodes:
        if isinstance(node, TextNode):
            value = _inline_text(node, scope, filename, lexical=lexical)
            if value:
                result.append(Text(value))
        elif isinstance(node, Fragment):
            result.append(VFragment(*_nodes(node.children, scope, primitives, filename, lexical=lexical)))
        else:
            result.append(_element(node, scope, primitives, filename, lexical=lexical))
    return result


def _element(
    element: Element,
    scope: Mapping[str, object],
    primitives: Mapping[str, Primitive],
    filename: str,
    *,
    lexical: bool,
) -> VNode:
    props = {
        attribute.name: _resolve_value(attribute.value, scope, filename, lexical=lexical)
        for attribute in element.attributes
    }
    constructor = primitives.get(element.name)
    if constructor is None:
        candidate = scope.get(element.name)
        if lexical and candidate is not None:
            candidate = _resolve_lexical_root(candidate, element.name, filename, element.span)
        if not isinstance(candidate, ComponentType):
            _error(f"Unknown PSX tag <{element.name}>", filename, element.span)
        constructor = candidate
    key = props.pop("key", None)
    if element.name == "Text":
        value = props.pop("value", None)
        content = _inline_children(element.children, scope, filename, lexical=lexical)
        if value is not None and content:
            _error("Text cannot receive both value and child text", filename, element.span)
        if value is None:
            value = content
        return Text(_text_value(value, filename, element.span), key=key, **props)
    if element.name == "Button":
        label = props.pop("label", None)
        content = _inline_children(element.children, scope, filename, lexical=lexical)
        if label is not None and content:
            _error("Button cannot receive both label and child text", filename, element.span)
        if label is None:
            label = content
        return Button(_text_value(label, filename, element.span), key=key, **props)
    children = _nodes(element.children, scope, primitives, filename, lexical=lexical)
    props = _coerce_host_props(element.name, props, filename, element.span)
    if constructor is Column or constructor is Row or constructor is VFragment:
        return constructor(*children, key=key, **props)
    if isinstance(constructor, ComponentType):
        return constructor(*children, key=key, **props)
    if callable(constructor):
        return constructor(*children, key=key, **props)
    return create_element(constructor, *children, key=key, **props)


def _resolve_value(
    value: AttributeValue, scope: Mapping[str, object], filename: str, *, lexical: bool
) -> object:
    return _resolve_reference(value, scope, filename, lexical=lexical) if isinstance(value, Reference) else value


def _resolve_reference(
    reference: Reference, scope: Mapping[str, object], filename: str, *, lexical: bool
) -> object:
    if reference.path[0] not in scope:
        _error(
            f"Unknown identifier {reference.path[0]!r}; pass it through scope={{...}} or use the M4B transform",
            filename,
            reference.span,
        )
    value = scope[reference.path[0]]
    if lexical:
        value = _resolve_lexical_root(value, reference.path[0], filename, reference.span)
    for segment in reference.path[1:]:
        if isinstance(value, Mapping):
            if segment not in value:
                _error(f"Mapping has no key {segment!r}", filename, reference.span)
            value = value[segment]
        elif lexical:
            try:
                value = getattr(value, segment)
            except AttributeError:
                _error(
                    f"Invalid lexical attribute path {'.'.join(reference.path)!r}; {segment!r} is unavailable",
                    filename,
                    reference.span,
                )
        else:
            _error("Dotted references are allowed only on mapping values in M4A", filename, reference.span)
    return value


def _resolve_lexical_root(value: object, name: str, filename: str, span: object) -> object:
    if not callable(value):
        _error("Invalid M4B lexical scope entry", filename, span)
    try:
        return value()
    except NameError:
        _error(f"Unknown lexical identifier {name!r}", filename, span)


def _inline_children(
    children: tuple[Node, ...], scope: Mapping[str, object], filename: str, *, lexical: bool
) -> str:
    values: list[str] = []
    for child in children:
        if not isinstance(child, TextNode):
            _error("Only text interpolation is allowed inside Text and Button in M4A", filename, child.span)
        values.append(_inline_text(child, scope, filename, lexical=lexical))
    return _normalize_text("".join(values))


def _inline_text(node: TextNode, scope: Mapping[str, object], filename: str, *, lexical: bool) -> str:
    output: list[str] = []
    for part in node.parts:
        if isinstance(part, TextPart):
            output.append(part.value)
        else:
            output.append(str(_resolve_reference(part.reference, scope, filename, lexical=lexical)))
    return _normalize_text("".join(output))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _text_value(value: object, filename: str, span: object) -> str | int | float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        _error("Text and Button content must resolve to str, int, or float", filename, span)
    return value


def _coerce_host_props(name: str, props: dict[str, object], filename: str, span: object) -> dict[str, object]:
    if name in {"Column", "Row"}:
        for prop in ("spacing", "padding"):
            if not isinstance(props.get(prop), str):
                continue
            try:
                props[prop] = int(props[prop])
            except ValueError:
                _error(f"{prop} must be an integer or an integer-valued reference", filename, span)
    return props


def _error(message: str, filename: str, span: object) -> None:
    line = getattr(span, "line")
    column = getattr(span, "column")
    raise MarkupSyntaxError(message, filename=filename, line=line, column=column)
