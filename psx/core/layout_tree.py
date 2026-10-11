"""F3-G1: immutable, renderer-neutral normalization of declarative Flex trees.

This is a structural hand-off contract, not a layout engine or reconciler.
No component is evaluated here: G2 supplies already-rendered component roots
from its mounted reconciler (which owns hooks, refs and component lifecycle).
Fragment/component boundaries remain observable but do not create SFLE boxes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .layout_item import validate_flex_item_props
from .props import FLEX_ITEM_PROPS
from .errors import DuplicateKeyError, RendererCapabilityError
from .vnode import NodeKind, VNode

PathSegment: TypeAlias = tuple[str, str | int]
LayoutPath: TypeAlias = tuple[PathSegment, ...]
_TRANSPARENT = frozenset((NodeKind.FRAGMENT, NodeKind.COMPONENT))
_MAX_DEPTH = 128


@dataclass(frozen=True, slots=True)
class NormalizedLayoutNode:
    """One original VNode and its normalized children, with stable keyed path.

    Paths name declarative identities, not widget handles or pixel boxes.
    Keys take precedence over sibling indices so keyed moves retain identity.
    Unkeyed moves retain positional semantics, as in the PSX reconciler.
    """

    source: VNode
    path: LayoutPath
    children: tuple["NormalizedLayoutNode", ...]

    @property
    def kind(self) -> NodeKind:
        return self.source.kind

    @property
    def type(self) -> object:
        return self.source.type

    def _participating_roots(self) -> tuple["NormalizedLayoutNode", ...]:
        if self.kind in _TRANSPARENT:
            return self.effective_children
        return (self,)

    @property
    def effective_children(self) -> tuple["NormalizedLayoutNode", ...]:
        """Direct layout participants, without fabricated wrapper boxes."""
        participants: list[NormalizedLayoutNode] = []
        for child in self.children:
            participants.extend(child._participating_roots())
        return tuple(participants)

    @property
    def scroll_content_root(self) -> "NormalizedLayoutNode | None":
        """The one explicit Flex root for a Scroll host, if applicable."""
        if self.kind is NodeKind.HOST and self.type == "Scroll":
            participants = self.effective_children
            # The normalizer has already rejected missing/ambiguous roots.
            return participants[0]
        return None


def normalize_flex_tree(
    root: VNode,
    *,
    component_roots: Mapping[int, VNode] | None = None,
) -> NormalizedLayoutNode:
    """Normalize an immutable PSX tree for the eventual SFLE coordinator.

    component_roots maps id(component_vnode) to its already rendered
    single-root VNode. Do not call a component's render function here: that
    would execute hooks without a mounted reconciliation boundary. G2 will
    supply these values from mounted instances.

    Scroll policy for SFLE: its effective content has exactly one explicit
    Flex root. Fragments and resolved single-root components can transparently
    expose that Flex; no native Flex, fallback Box or layout wrapper is inserted.
    Existing pre-SFLE native Scroll behavior is not altered by this pure
    normalization function and will be migrated as part of G3/G4.
    """
    if not isinstance(root, VNode):
        raise TypeError("normalize_flex_tree requires a VNode.")
    resolved = component_roots if component_roots is not None else {}
    # Registry lookup is local and does not load optional GUI libraries.
    # Extension hosts without a core contract retain their custom props;
    # their SFLE metadata must still validate identically.
    from .registry import builtin_component_registry
    definitions = builtin_component_registry().snapshot()

    def visit(
        node: VNode, path: LayoutPath, active: frozenset[int],
        depth: int,
    ) -> NormalizedLayoutNode:
        if depth > _MAX_DEPTH or id(node) in active:
            raise RendererCapabilityError("Cyclic or excessively deep PSX layout tree.")
        next_active = active | {id(node)}

        if node.kind is NodeKind.COMPONENT:
            rendered = resolved.get(id(node))
            if not isinstance(rendered, VNode):
                raise RendererCapabilityError(
                    "Flex layout requires the resolved single root of each "
                    "function component from the reconciler."
                )
            children = (
                visit(rendered, path + (("rendered", 0),), next_active, depth + 1),
            )
        else:
            if node.kind is NodeKind.HOST:
                definition = definitions.get(node.type) if isinstance(node.type, str) else None
                if definition is not None and definition.contract is not None:
                    definition.contract.validate(node.props)
                else:
                    validate_flex_item_props(node.props, owner=str(node.type))
                    if node.type == "Box":
                        invalid = set(node.props) - {"ref"} - FLEX_ITEM_PROPS
                        if invalid:
                            raise RendererCapabilityError(
                                f"Unsupported Box props: {', '.join(sorted(invalid))}.")
            elif node.kind is NodeKind.NATIVE:
                validate_flex_item_props(node.props, owner="Native")
            elif node.kind is NodeKind.FRAGMENT and node.props:
                raise RendererCapabilityError("Fragment does not accept layout metadata.")
            seen: set[str | int] = set()
            for child in node.children:
                if child.key is None:
                    continue
                if child.key in seen:
                    raise DuplicateKeyError(
                        f"Duplicate key {child.key!r} in normalized layout children."
                    )
                seen.add(child.key)

            children = tuple(
                visit(
                    child,
                    path + ((("key", child.key) if child.key is not None
                             else ("index", index)),),
                    next_active,
                    depth + 1,
                )
                for index, child in enumerate(node.children)
            )

        result = NormalizedLayoutNode(node, path, children)
        if node.kind is NodeKind.HOST and node.type == "Scroll":
            participants = result.effective_children
            if len(participants) != 1 or (
                participants[0].kind is not NodeKind.HOST
                or participants[0].type != "Flex"
            ):
                raise RendererCapabilityError(
                    "Scroll SFLE content must have exactly one explicit Flex root; "
                    "use <Scroll><Flex>...</Flex></Scroll>."
                )
        return result

    return visit(root, (("root", 0),), frozenset(), 0)
