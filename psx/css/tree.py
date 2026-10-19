"""Internal, read-only PSX VNode style-tree projection.

Style metadata is supplied out of band until the public stylesheet attachment,
class/id and precedence contract is approved. The original VNodes, keys,
component props and native resource owners are never changed or retained.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from psx.core.vnode import NodeKind, VNode
from .cascade import ComputedStyle, StyleTarget, resolve_style
from .parser import Stylesheet
from .properties import CssDeclaration

NodePath = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StyledNode:
    path: NodePath
    key: str | int | None
    tag: str
    computed: ComputedStyle


def resolve_vnode_styles(
    root: VNode,
    stylesheet: Stylesheet,
    *,
    selectors: Mapping[NodePath, StyleTarget] | None = None,
    inline: Mapping[NodePath, tuple[CssDeclaration, ...]] | None = None,
) -> tuple[StyledNode, ...]:
    """Return detached style records without injecting any new public VNode props.

    Component and native nodes are opaque, as their mounted trees and owned
    native handles cannot be derived from a VNode declaration.
    """
    select = {} if selectors is None else selectors
    declarations = {} if inline is None else inline
    result: list[StyledNode] = []

    def visit(node: VNode, path: NodePath, inherited: ComputedStyle | None) -> None:
        if node.kind is not NodeKind.HOST:
            return
        if not isinstance(node.type, str):
            return
        target = select.get(path, StyleTarget(node.type))
        if target.tag != node.type:
            raise ValueError(f"CSS selector tag does not match VNode type at {path!r}.")
        computed = resolve_style(
            stylesheet, target, inherited=inherited,
            inline=declarations.get(path, ()),
        )
        result.append(StyledNode(path, node.key, node.type, computed))
        for index, child in enumerate(node.children):
            visit(child, (*path, index), computed)

    visit(root, (), None)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class StyleTreeChange:
    """The new tree's path, identity and conservative change effect."""

    path: NodePath
    key: str | int | None
    effect: object
    added: bool = False
    removed: bool = False


def compare_styled_trees(
    previous: tuple[StyledNode, ...],
    current: tuple[StyledNode, ...],
) -> tuple[StyleTreeChange, ...]:
    """Compare immutable snapshots without retaining previous mounted trees.

    Keyed sibling identity is scoped to a parent path, mirroring PSX keys.
    Unkeyed identities remain positional. A relocated keyed child under a
    different parent is intentionally considered removed and added.
    """
    from .effects import StyleEffect, classify_style_change

    def identities(items: tuple[StyledNode, ...]) -> dict[tuple[object, ...], StyledNode]:
        result: dict[tuple[object, ...], StyledNode] = {}
        for item in items:
            identity = (
                ("key", item.path[:-1], item.key)
                if item.key is not None and item.path
                else ("path", item.path)
            )
            if identity in result:
                raise ValueError(f"Duplicate scoped CSS tree identity: {identity!r}.")
            result[identity] = item
        return result

    before = identities(previous)
    after = identities(current)
    changes: list[StyleTreeChange] = []
    for identity, item in after.items():
        old = before.get(identity)
        if old is None or old.tag != item.tag:
            changes.append(StyleTreeChange(item.path, item.key, StyleEffect.GEOMETRY | StyleEffect.MEASUREMENT | StyleEffect.PAINT, added=True))
            continue
        effect = classify_style_change(old.computed, item.computed)
        if effect:
            changes.append(StyleTreeChange(item.path, item.key, effect))
    for identity, item in before.items():
        if identity not in after or after[identity].tag != item.tag:
            changes.append(StyleTreeChange(item.path, item.key, StyleEffect.GEOMETRY | StyleEffect.MEASUREMENT | StyleEffect.PAINT, removed=True))
    return tuple(changes)
