"""Safe M4A AST compiler: explicit scope, no eval/exec/frame inspection."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from psx.core.component import ComponentType
from psx.core.errors import MarkupSyntaxError
from psx.core.registry import ComponentDefinition, ComponentRegistry, builtin_component_registry
from psx.core.vnode import Fragment as VFragment, Text, VNode

from .ast import (
    AttributeValue,
    Document,
    Element,
    Fragment,
    Node,
    Reference,
    ReferencePart,
    TextNode,
    TextPart,
)
from .parser import parse

Primitive: TypeAlias = Callable[..., VNode] | ComponentType
_GRAMMAR_VERSION = "m4a-1"
_CACHE_LIMIT = 128
_CACHE: "OrderedDict[tuple[str, str, str, Hashable], CompiledTemplate]" = OrderedDict()


@dataclass(frozen=True, slots=True)
class _Resolver:
    definitions: Mapping[str, ComponentDefinition]
    cache_key: Hashable

    def resolve(self, name: str) -> ComponentDefinition | None:
        return self.definitions.get(name)

    @property
    def primitives(self) -> Mapping[str, Primitive]:
        return {name: definition.constructor for name, definition in self.definitions.items()}


@dataclass(frozen=True, slots=True)
class CompiledTemplate:
    document: Document
    filename: str
    resolver: _Resolver

    @property
    def primitives(self) -> Mapping[str, Primitive]:
        """Compatibility view of constructors available to this template."""
        return self.resolver.primitives

    def render(self, scope: Mapping[str, object] | None = None) -> VNode:
        values = {} if scope is None else scope
        children = _nodes(self.document.children, values, self.resolver, self.filename, lexical=False)
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
        children = _nodes(self.document.children, scope, self.resolver, self.filename, lexical=True)
        if len(children) == 1:
            return children[0]
        return VFragment(*children)


def compile_template(
    source: str,
    *,
    filename: str = "<psx>",
    primitives: Mapping[str, Primitive] | None = None,
    registry: ComponentRegistry | None = None,
) -> CompiledTemplate:
    """Compile markup using legacy primitives or an isolated component registry.

    ``registry`` is additive. Passing neither retains the default built-ins;
    passing ``primitives`` retains the legacy replacement-mapping behavior.
    """
    resolver = _resolver(primitives=primitives, registry=registry)
    key = (source, filename, _GRAMMAR_VERSION, resolver.cache_key)
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached
    compiled = CompiledTemplate(parse(source, filename=filename), filename, resolver)
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
    registry: ComponentRegistry | None = None,
) -> VNode:
    """Compile and render an explicit-scope PSX template into ordinary VNodes."""
    return compile_template(source, filename=filename, primitives=primitives, registry=registry).render(scope)


def clear_template_cache() -> None:
    _CACHE.clear()


def _resolver(
    *, primitives: Mapping[str, Primitive] | None, registry: ComponentRegistry | None
) -> _Resolver:
    if primitives is not None and registry is not None:
        raise TypeError("Pass either primitives or registry, not both.")
    if registry is not None:
        return _Resolver(registry.snapshot(), ("registry", id(registry), registry.version))
    builtins = builtin_component_registry()
    if primitives is None:
        # Fresh default registries have the same built-in contents. Their
        # cache identity is deliberately stable while caller-owned registries
        # are always isolated by object identity and version.
        return _Resolver(builtins.snapshot(), ("default-builtins", builtins.version))
    builtin_definitions = builtins.snapshot()
    definitions = {
        name: ComponentDefinition(
            name,
            constructor,
            contract=builtin_definitions[name].contract if name in builtin_definitions else None,
            markup_integer_properties=(
                builtin_definitions[name].markup_integer_properties if name in builtin_definitions else frozenset()
            ),
        )
        for name, constructor in primitives.items()
    }
    return _Resolver(definitions, ("primitives", id(primitives)))


def _nodes(
    nodes: tuple[Node, ...],
    scope: Mapping[str, object],
    resolver: _Resolver,
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
            result.append(VFragment(*_nodes(node.children, scope, resolver, filename, lexical=lexical)))
        else:
            result.append(_element(node, scope, resolver, filename, lexical=lexical))
    return result


def _element(
    element: Element,
    scope: Mapping[str, object],
    resolver: _Resolver,
    filename: str,
    *,
    lexical: bool,
) -> VNode:
    props = {
        attribute.name: _resolve_value(attribute.value, scope, filename, lexical=lexical)
        for attribute in element.attributes
    }
    definition = resolver.resolve(element.name)
    if definition is None:
        candidate = scope.get(element.name)
        if lexical and candidate is not None:
            candidate = _resolve_lexical_root(candidate, element.name, filename, element.span)
        if not isinstance(candidate, ComponentType):
            _error(f"Unknown PSX tag <{element.name}>", filename, element.span)
        definition = ComponentDefinition(element.name, candidate)
    constructor = definition.constructor
    key = props.pop("key", None)
    contract = definition.contract
    if contract is not None and contract.child_policy == "none-or-single":
        meaningful = _meaningful_children(element.children)
        if len(meaningful) > 1:
            _error(
                f"{definition.name} accepts at most one child",
                filename,
                element.span,
            )
        children = _nodes(meaningful, scope, resolver, filename, lexical=lexical)
        props = _coerce_props(definition, props, filename, element.span)
        return constructor(*children, key=key, **props)
    if contract is not None and contract.content_property is not None:
        property_name = contract.content_property
        value = props.pop(property_name, None)
        content = _inline_children(element.children, scope, filename, lexical=lexical)
        if value is not None and content:
            _error(f"{definition.name} cannot receive both {property_name} and child text", filename, element.span)
        if value is None:
            value = content
        return constructor(_text_value(value, filename, element.span), key=key, **props)
    if contract is not None and contract.child_policy == "none" and element.children:
        _error(f"{definition.name} does not accept child content; use its props instead", filename, element.span)
    children = _nodes(element.children, scope, resolver, filename, lexical=lexical)
    props = _coerce_props(definition, props, filename, element.span)
    return constructor(*children, key=key, **props)


def _meaningful_children(nodes: tuple[Node, ...]) -> tuple[Node, ...]:
    """Filtra TextNode que no aportan contenido (whitespace estructural).

    El markup multilínea genera TextNode con newlines e indentación alrededor
    de los hijos reales. Para contratos con child policy estricta
    (``none-or-single``), esos nodos no deben contar como hijos. Un TextNode
    con al menos una ReferencePart sí cuenta, aunque su parte literal sea
    solo whitespace.
    """
    result: list[Node] = []
    for child in nodes:
        if isinstance(child, TextNode):
            has_reference = any(
                isinstance(part, ReferencePart) for part in child.parts
            )
            if not has_reference:
                literal = "".join(
                    part.value for part in child.parts if isinstance(part, TextPart)
                )
                if not _normalize_text(literal):
                    continue
        result.append(child)
    return tuple(result)


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


def _coerce_props(
    definition: ComponentDefinition, props: dict[str, object], filename: str, span: object
) -> dict[str, object]:
    for prop in definition.markup_integer_properties:
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