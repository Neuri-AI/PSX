"""Safe M4A AST compiler: explicit scope, no eval/exec/frame inspection."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, replace
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
from .html_aliases import markup_alias_definitions, PORTABLE_HTML_ALIASES
from .html_form_groups import compose_html_radio_groups
from psx.css.markup import compute_markup_styles, parse_markup_style
from psx.css.parser import CssSyntaxError
from psx.css.sources import CssSourceManager

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
        root = children[0] if len(children) == 1 else VFragment(*children)
        return _apply_document_css(compose_html_radio_groups(root), self.document, values)

    def render_lexical(self, scope: Mapping[str, object]) -> VNode:
        """Render M4B static lexical scope without evaluating template expressions.

        Values are generated source-transform thunks for lexical root names. The
        only dynamic traversal performed here is a parser-validated dotted
        attribute/mapping path; callables obtained along a path are returned,
        never invoked.
        """
        children = _nodes(self.document.children, scope, self.resolver, self.filename, lexical=True)
        root = children[0] if len(children) == 1 else VFragment(*children)
        return _apply_document_css(compose_html_radio_groups(root), self.document, scope)


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
        return _Resolver(markup_alias_definitions(registry.snapshot()), ("registry-html-aliases", id(registry), registry.version))
    builtins = builtin_component_registry()
    if primitives is None:
        # Fresh default registries have the same built-in contents. Their
        # cache identity is deliberately stable while caller-owned registries
        # are always isolated by object identity and version.
        return _Resolver(markup_alias_definitions(builtins.snapshot()), ("default-builtins-html-aliases", builtins.version))
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
    preserve_text_edges: bool = False,
) -> list[VNode]:
    result: list[VNode] = []
    for node in nodes:
        if isinstance(node, TextNode):
            value = (
                _inline_text_preserving_edges(node, scope, filename, lexical=lexical)
                if preserve_text_edges else _inline_text(node, scope, filename, lexical=lexical)
            )
            if value:
                result.append(replace(Text(value), css_source=parse_markup_style("__psx_text_content__")))
        elif isinstance(node, Fragment):
            result.append(VFragment(*_nodes(node.children, scope, resolver, filename, lexical=lexical)))
        elif isinstance(node, Element) and node.name == 'link':
            _validate_stylesheet_link(node)
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
    css_source = None
    # Public PascalCase native controls share the same CSS surface as their
    # HTML-like aliases. Custom lexical components remain opt-in/opaque.
    css_native_tags = {
        "Button": "button", "Input": "input", "TextArea": "textarea",
        "Checkbox": "checkbox", "Radio": "radio", "Select": "select",
        "Link": "link", "Badge": "badge", "SpinBox": "spinbox",
        "Text": "text", "Flex": "flex", "Grid": "grid",
        "GridItem": "griditem", "Box": "box", "Scroll": "scroll",
        "Slider": "slider", "Spacer": "spacer", "Divider": "divider",
        "Image": "image", "ProgressBar": "progressbar",
        "RadioGroup": "radiogroup", "Switch": "switch",
    }
    if element.name in PORTABLE_HTML_ALIASES or element.name in css_native_tags:
        if "class" in props and "class_name" in props:
            _error("Use either class or class_name, not both.", filename, element.span)
        css_class = props.pop("class", None)
        if css_class is None:
            css_class = props.pop("class_name", None)
        inline_value = props.pop("style", None)
        try:
            css_source = parse_markup_style(
                css_native_tags.get(element.name, element.name), class_value=css_class,
                id_value=props.pop("id", None), inline_value=inline_value,
            )
        except CssSyntaxError as exc:
            # Preserve the existing semantic-host unsupported-property
            # diagnostic while retaining the exact CSS validation reason.
            raise ValueError(
                f"Unsupported {element.name} properties: ['style']; {exc}"
            ) from exc
    props = _coerce_props(definition, props, filename, element.span)
    contract = definition.contract
    def finish(node: VNode) -> VNode:
        return replace(node, css_source=css_source) if css_source is not None else node
    if contract is not None and contract.child_policy == "none-or-single":
        meaningful = _meaningful_children(element.children)
        if len(meaningful) > 1:
            _error(
                f"{definition.name} accepts at most one child",
                filename,
                element.span,
            )
        children = _nodes(meaningful, scope, resolver, filename, lexical=lexical)
        return finish(constructor(*children, key=key, **props))
    if contract is not None and contract.content_property is not None:
        property_name = contract.content_property
        value = props.pop(property_name, None)
        content = _inline_children(element.children, scope, filename, lexical=lexical)
        if value is not None and content:
            _error(f"{definition.name} cannot receive both {property_name} and child text", filename, element.span)
        if value is None:
            value = content
        return finish(constructor(_text_value(value, filename, element.span), key=key, **props))
    if contract is not None and contract.child_policy == "text":
        value = props.pop("value", None)
        content = _inline_children(element.children, scope, filename, lexical=lexical)
        if value is not None and content:
            _error(f"{definition.name} cannot receive both value and child text", filename, element.span)
        if value is None:
            value = content
        return finish(constructor(_text_value(value, filename, element.span), key=key, **props))
    if contract is not None and contract.child_policy == "none" and element.children:
        _error(f"{definition.name} does not accept child content; use its props instead", filename, element.span)
    # Preserve the spaces bordering inline tags: trimming every TextNode
    # independently turns 'Edit <span>path</span> and save' into 'Editpathand
    # save'. Structural newline-only indentation remains discarded by the
    # normal parser for other (non-mixed) elements.
    from psx.markup.html_aliases import FORMATTING_TAGS
    mixed_inline = (
        element.name in FORMATTING_TAGS
        and any(isinstance(child, Element) and child.name in ("span", "label")
                for child in element.children)
    )
    children = _nodes(
        element.children, scope, resolver, filename, lexical=lexical,
        preserve_text_edges=mixed_inline,
    )
    return finish(constructor(*children, key=key, **props))


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


def _inline_text_preserving_edges(
    node: TextNode, scope: Mapping[str, object], filename: str, *, lexical: bool
) -> str:
    # HTML white-space:normal collapses internal runs but retains a single
    # boundary space on either side of inline markup. Never strip each text
    # sibling independently; the inline formatting run owns line edges.
    output = []
    for part in node.parts:
        if isinstance(part, TextPart):
            output.append(part.value)
        else:
            output.append(str(_resolve_reference(part.reference, scope, filename, lexical=lexical)))
    return re.sub(r"\s+", " ", "".join(output))


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


_QUOTED_NUMERIC_PROPS = frozenset({
    "gap", "row_gap", "column_gap", "spacing", "padding",
    "font_size", "width", "height", "min_width", "min_height",
    "max_width", "max_height", "layout_width", "layout_height",
    "layout_min_width", "layout_min_height", "layout_max_width",
    "layout_max_height", "flex_grow", "flex_shrink", "flex_basis",
    "order", "thickness", "decimals", "span", "offset",
})


def _coerce_props(
    definition: ComponentDefinition, props: dict[str, object], filename: str, span: object
) -> dict[str, object]:
    # Attribute braces are references, not literal markers. Preserve numeric
    # properties' existing Python values when the developer uses quoted,
    # unitless literals (gap="12"); unit-bearing lengths remain strings.
    for prop, value in tuple(props.items()):
        if prop not in _QUOTED_NUMERIC_PROPS or not isinstance(value, str):
            continue
        import re
        if re.fullmatch(r"[+-]?(?:[0-9]+(?:\\.[0-9]+)?|\\.[0-9]+)", value):
            props[prop] = float(value) if "." in value else int(value)
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


def _has_css_source(node: VNode) -> bool:
    source = node.css_source
    has_declarations = source is not None and bool(source.classes or source.node_id or source.inline)
    return has_declarations or any(_has_css_source(child) for child in node.children)

def _validate_stylesheet_link(element: Element) -> str:
    if element.children:
        raise ValueError("CSS link cannot contain children.")
    values = {attribute.name: attribute.value for attribute in element.attributes}
    if set(values) != {"rel", "href"} or values["rel"] != "stylesheet":
        raise ValueError('link requires rel="stylesheet" and href="...css".')
    href = values["href"]
    if not isinstance(href, str) or not href.endswith(".css"):
        raise ValueError("Stylesheet href must be a local .css resource.")
    return href


def _document_stylesheets(nodes: tuple[Node, ...]) -> tuple[str, ...]:
    references: list[str] = []
    for node in nodes:
        if isinstance(node, Element):
            if node.name == "link":
                references.append(_validate_stylesheet_link(node))
            else:
                references.extend(_document_stylesheets(node.children))
        elif isinstance(node, Fragment):
            references.extend(_document_stylesheets(node.children))
    return tuple(references)


def _apply_document_css(root: VNode, document: Document, scope: Mapping[str, object]) -> VNode:
    references = _document_stylesheets(document.children)
    from psx.css.context import current_css_context
    context = current_css_context()
    globals_ = scope.get("__velto_stylesheets__", context.stylesheets if context else ())
    if not isinstance(globals_, (list, tuple)) or any(not isinstance(item, str) for item in globals_):
        raise TypeError("Global CSS stylesheet paths must be a string sequence.")
    all_sources = (*globals_, *references)
    if not all_sources and not _has_css_source(root):
        return root
    resource_resolver = scope.get("__velto_css_resource_resolver__", context.resolver if context else None)
    if resource_resolver is not None and not callable(resource_resolver):
        raise TypeError("CSS resource resolver must be callable.")
    source_root = scope.get("__velto_css_root__", context.root if context else ".")
    manager = CssSourceManager(resource_resolver, root=source_root)
    compiled = manager.load(all_sources) if all_sources else None
    return compute_markup_styles(root, compiled)
