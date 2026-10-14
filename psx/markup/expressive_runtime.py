"""Runtime construction helpers for statically transformed M4B conditional markup.

These functions receive ordinary values from precompiled Python expressions.
They never parse Python source, evaluate code strings or inspect call frames.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Callable

from psx.core.component import ComponentType
from psx.core.errors import InvalidChildError, MarkupSyntaxError
from psx.core.registry import builtin_component_registry
from psx.core.vnode import Fragment, Text, VNode
from .compile import _coerce_props

_BUILTINS = builtin_component_registry().snapshot()


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


def conditional(value: object) -> object:
    """A conditional branch contributes no VNode when its result is falsy."""
    return value if value else None


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
    if definition is not None:
        from .ast import Span
        props = _coerce_props(definition, props, filename, Span(0, line, column))
    contract = definition.contract if definition else None
    if contract is not None and contract.content_property is not None:
        prop = contract.content_property
        value = props.pop(prop, None)
        content = "".join(str(x) for x in children if x is not None and x is not False)
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
        return constructor(value, key=key, **props)
    if contract is not None and contract.child_policy == "none" and any(
        x is not None and x is not False for x in children
    ):
        raise MarkupSyntaxError(
            f"{name} does not accept children", filename=filename, line=line, column=column
        )
    normalized = tuple(_flatten(children))
    if contract is not None and contract.child_policy == "none-or-single" and len(normalized) > 1:
        raise MarkupSyntaxError(
            f"{name} accepts at most one child", filename=filename, line=line, column=column
        )
    return constructor(*normalized, key=key, **props)
