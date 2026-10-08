"""Immutable UI descriptions and the canonical Python element constructors."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, TypeAlias

from .errors import InvalidChildError
from .native import NativeWidget

if TYPE_CHECKING:
    from .component import ComponentType


class NodeKind(str, Enum):
    HOST = "host"
    COMPONENT = "component"
    FRAGMENT = "fragment"
    NATIVE = "native"


HostType: TypeAlias = str
# ComponentType is intentionally not imported at module load time to avoid the
# component/vnode import cycle. Runtime validation in create_element is exact.
VNodeType: TypeAlias = object
Key: TypeAlias = str | int


@dataclass(frozen=True, slots=True)
class VNode:
    """A framework-independent, immutable UI description.

    Native widget handles belong to mounted instances, never to this value.
    """

    kind: NodeKind
    type: VNodeType
    key: Key | None
    props: Mapping[str, object]
    children: tuple["VNode", ...]


def _freeze_props(props: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(props))


def _normalize_one(value: object, output: list[VNode]) -> None:
    if value is None or value is False:
        return
    if isinstance(value, VNode):
        output.append(value)
        return
    if isinstance(value, str):
        output.append(Text(value))
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        output.append(Text(str(value)))
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _normalize_one(child, output)
        return
    if value is True:
        raise InvalidChildError("True is not a valid PSX child; use a conditional expression instead.")
    raise InvalidChildError(f"Unsupported PSX child: {type(value).__name__}")


def normalize_children(values: Iterable[object]) -> tuple[VNode, ...]:
    """Normalize supported declarative child values into immutable VNodes."""
    output: list[VNode] = []
    for value in values:
        _normalize_one(value, output)
    return tuple(output)


def create_element(
    node_type: VNodeType,
    *children: object,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Create a VNode; all public builders delegate to this constructor."""
    from .component import ComponentType

    if key is not None and not isinstance(key, (str, int)):
        raise TypeError("PSX keys must be str, int, or None.")
    if ref is not None:
        props["ref"] = ref
    if isinstance(node_type, ComponentType):
        kind = NodeKind.COMPONENT
    elif node_type is Fragment:
        kind = NodeKind.FRAGMENT
        node_type = "Fragment"
    elif isinstance(node_type, str):
        kind = NodeKind.HOST
    elif isinstance(node_type, NativeWidget):
        kind = NodeKind.NATIVE
        if children:
            raise InvalidChildError("Native widgets cannot have PSX children; compose them in a layout instead.")
    else:
        raise TypeError("PSX element type must be a host name, Fragment, NativeWidget, or @component value.")
    return VNode(kind, node_type, key, _freeze_props(props), normalize_children(children))


class _Fragment:
    def __call__(self, *children: object, key: Key | None = None) -> VNode:
        return create_element(self, *children, key=key)

    def __repr__(self) -> str:
        return "Fragment"


Fragment = _Fragment()


def native_widget(
    widget: NativeWidget, *, key: Key | None = None, ref: object | None = None, **props: object
) -> VNode:
    """Create a VNode for a renderer-specific :class:`NativeWidget` declaration."""
    if not isinstance(widget, NativeWidget):
        raise TypeError("native_widget() requires a NativeWidget declaration.")
    return create_element(widget, key=key, ref=ref, **props)


def _layout(name: str, children: tuple[object, ...], spacing: int, key: Key | None, props: Mapping[str, object]) -> VNode:
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise ValueError("spacing must be a non-negative integer.")
    return create_element(name, *children, key=key, spacing=spacing, **props)


def Column(*children: object, spacing: int = 0, key: Key | None = None, **props: object) -> VNode:
    return _layout("Column", children, spacing, key, props)


def Row(*children: object, spacing: int = 0, key: Key | None = None, **props: object) -> VNode:
    return _layout("Row", children, spacing, key, props)


def Text(value: str | int | float, *, key: Key | None = None, **props: object) -> VNode:
    if isinstance(value, bool):
        raise TypeError("Text value must be str, int, or float, not bool.")
    if not isinstance(value, (str, int, float)):
        raise TypeError("Text value must be str, int, or float.")
    return create_element("Text", key=key, value=str(value), **props)


def Button(
    label: str | int | float,
    *,
    on_click: Callable[[], None] | None = None,
    enabled: bool = True,
    key: Key | None = None,
    **props: object,
) -> VNode:
    if isinstance(label, bool):
        raise TypeError("Button label must be str, int, or float, not bool.")
    if not isinstance(enabled, bool):
        raise TypeError("enabled must be a bool.")
    return create_element(
        "Button", key=key, label=str(label), on_click=on_click, enabled=enabled, **props
    )
