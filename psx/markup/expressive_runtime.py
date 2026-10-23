"""Runtime construction helpers for statically transformed M4B conditional markup.

These functions receive ordinary values from precompiled Python expressions.
They never parse Python source, evaluate code strings or inspect call frames.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Callable

from psx.core.component import ComponentType
from psx.core.errors import InvalidChildError, MarkupSyntaxError
from psx.core.registry import builtin_component_registry
from psx.core.vnode import Fragment, Text, VNode
from .compile import _coerce_props
from psx.css.markup import compute_expressive_markup_styles
from .html_aliases import markup_alias_definitions, PORTABLE_HTML_ALIASES
from psx.css.markup import parse_markup_style

_BUILTINS = markup_alias_definitions(builtin_component_registry().snapshot())


def lexical(thunk: Callable[[], object], name: str, filename: str, line: int, column: int) -> object:
    """Resolve a static Python lexical binding with a markup source diagnostic."""
    try:
        return thunk()
    except NameError as error:
        raise MarkupSyntaxError(
            f"Unknown lexical identifier {name!r}",
            filename=filename, line=line, column=column,
        ) from error


def member(value: object, attribute: str, filename: str, line: int, column: int) -> object:
    # Expressive markup only supports public model fields; never expose
    # Python runtime/introspection internals through JSX member syntax.
    if attribute.startswith("_"):
        raise MarkupSyntaxError(
            f"Private lexical attribute {attribute!r} is not accessible",
            filename=filename, line=line, column=column,
        )
    if isinstance(value, Mapping):
        if attribute in value:
            return value[attribute]
    else:
        try:
            return getattr(value, attribute)
        except AttributeError:
            pass
    raise MarkupSyntaxError(
        f"Invalid lexical attribute {attribute!r}",
        filename=filename, line=line, column=column,
    )


def index(value: object, position: object, filename: str, line: int, column: int) -> object:
    """Read a bounded public sequence index or mapping key in M4B markup."""
    if isinstance(value, (list, tuple)):
        if isinstance(position, bool) or not isinstance(position, int):
            raise MarkupSyntaxError("Sequence indices must be integers", filename=filename, line=line, column=column)
    elif isinstance(value, Mapping):
        if not isinstance(position, (str, int)) or isinstance(position, bool) or (isinstance(position, str) and position.startswith("_")):
            raise MarkupSyntaxError("Unsupported mapping key", filename=filename, line=line, column=column)
    else:
        raise MarkupSyntaxError("Indexing requires a list, tuple, or mapping", filename=filename, line=line, column=column)
    try:
        return value[position]
    except (IndexError, KeyError, TypeError) as error:
        raise MarkupSyntaxError("Invalid sequence index or mapping key", filename=filename, line=line, column=column) from error


def conditional(value: object) -> object:
    """A conditional branch contributes no VNode when its result is falsy."""
    return value if value else None


def map_children(
    iterable: object, callback: Callable[..., object],
    with_index: bool, filename: str, line: int, column: int,
) -> tuple[VNode, ...]:
    """Materialize an ordered, keyed dynamic list once per render.

    No monkey-patching of list.map, no index-based keys and no unkeyed
    remount fallback. Validate the complete list before a native commit.
    """
    try:
        iterator = iter(iterable)
    except TypeError as error:
        raise MarkupSyntaxError(
            ".map() requires an iterable", filename=filename,
            line=line, column=column,
        ) from error
    result: list[VNode] = []
    keys: set[str | int] = set()
    for index, item in enumerate(iterator):
        output = callback(item, index) if with_index else callback(item)
        if output is None or output is False:
            continue
        if not isinstance(output, VNode):
            raise MarkupSyntaxError(
                ".map() must produce a keyed VNode or an absent conditional node",
                filename=filename, line=line, column=column,
            )
        key = output.key
        if key is None or isinstance(key, bool) or not isinstance(key, (str, int)):
            raise MarkupSyntaxError(
                ".map() elements require a stable string/integer key",
                filename=filename, line=line, column=column,
            )
        if key in keys:
            raise MarkupSyntaxError(
                f"Duplicate .map() key {key!r}",
                filename=filename, line=line, column=column,
            )
        keys.add(key)
        result.append(output)
    return tuple(result)


def _flatten(children: tuple[object, ...]):
    for child in children:
        if child is None or child is False:
            continue
        if isinstance(child, VNode):
            yield child
        elif isinstance(child, (tuple, list)):
            yield from _flatten(tuple(child))
        elif isinstance(child, (str, int, float)) and not isinstance(child, bool):
            # Standalone falsy scalars in a conditional child do not render.
            if child or isinstance(child, str) and child:
                yield Text(str(child))
        else:
            raise InvalidChildError(f"Unsupported expressive markup child {type(child).__name__}")


def fragment(*children: object) -> VNode:
    return Fragment(*tuple(_flatten(children)))


def element(
    name: str, props: dict[str, object], children: tuple[object, ...],
    filename: str, line: int, column: int, custom: object = None,
) -> VNode:
    definition = _BUILTINS.get(name)
    if definition is None:
        if not isinstance(custom, ComponentType):
            raise MarkupSyntaxError(
                f"Unknown PSX tag <{name}>", filename=filename, line=line, column=column
            )
        constructor = custom
    else:
        constructor = definition.constructor
    props = dict(props)
    key = props.pop("key", None)
    css_source = None
    if name in PORTABLE_HTML_ALIASES:
        if "class" in props and "class_name" in props:
            raise MarkupSyntaxError("Use either class or class_name", filename=filename, line=line, column=column)
        class_value = props.pop("class", None)
        if class_value is None:
            class_value = props.pop("class_name", None)
        css_source = parse_markup_style(
            name, class_value=class_value,
            id_value=props.pop("id", None),
            inline_value=props.pop("style", None),
        )
    def finish(node: VNode) -> VNode:
        return replace(node, css_source=css_source) if css_source is not None else node
    if definition is not None:
        from .ast import Span
        props = _coerce_props(definition, props, filename, Span(0, line, column))
    contract = definition.contract if definition else None
    if contract is not None and contract.content_property is not None:
        prop = contract.content_property
        value = props.pop(prop, None)
        text_parts: list[str] = []
        for part in children:
            if part is None or part is False:
                continue
            if isinstance(part, bool) or not isinstance(part, (str, int, float)):
                raise MarkupSyntaxError(
                    f"{name} accepts only textual content",
                    filename=filename, line=line, column=column,
                )
            text_parts.append(str(part))
        content = "".join(text_parts)
        if value is not None and content.strip():
            raise MarkupSyntaxError(
                f"{name} cannot receive both {prop} and child text",
                filename=filename, line=line, column=column,
            )
        if value is None:
            value = content.strip()
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise MarkupSyntaxError(
                f"{name} content must be str, int or float",
                filename=filename, line=line, column=column,
            )
        return finish(constructor(value, key=key, **props))
    if contract is not None and contract.child_policy == "none" and any(
        x is not None and x is not False for x in children
    ):
        raise MarkupSyntaxError(
            f"{name} does not accept children", filename=filename, line=line, column=column
        )
    normalized = tuple(_flatten(children))
    if name in ("p", "h1", "h2", "h3", "h4", "h5", "h6"):
        # Adjacent literal and expression text share one inline text box.
        # Independent native Text hosts would otherwise enter block flow on
        # separate lines even though they are one paragraph text run.
        joined = []
        for child in normalized:
            if (joined and child.type == "Text" and joined[-1].type == "Text"
                    and child.key is None and joined[-1].key is None
                    and child.css_source is None and joined[-1].css_source is None
                    and {k: v for k, v in child.props.items() if k != "value"}
                    == {k: v for k, v in joined[-1].props.items() if k != "value"}):
                previous = joined[-1]
                joined[-1] = Text(
                    str(previous.props["value"]) + str(child.props["value"]),
                    **{k: v for k, v in previous.props.items() if k != "value"},
                )
            else:
                joined.append(child)
        normalized = tuple(joined)
    if contract is not None and contract.child_policy == "none-or-single" and len(normalized) > 1:
        raise MarkupSyntaxError(
            f"{name} accepts at most one child", filename=filename, line=line, column=column
        )
    return finish(constructor(*normalized, key=key, **props))

# The lexical import hook already binds the element helper in every transformed
# module, so attach the CSS source resolver here instead of adding a new global.
element.compute_styles = compute_expressive_markup_styles
