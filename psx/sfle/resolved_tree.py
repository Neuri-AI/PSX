"""Restricted recursive Flex geometry using existing CSS-resolved kernels.

All container and item dimensions must be definite, zero-edge content boxes.
Auto/intrinsic/percentage sizing and native measurements belong to other stages.
Unlike the flat kernel, child Flex contexts are positioned in their parent.
"""
from __future__ import annotations
from dataclasses import dataclass
from .errors import DiagnosticCode, SFLEError
from .flex_math import FlexBasis
from .line_layout import FlexDirection, FlexWrap
from .model import BoxRect, LayoutResult, Rect, WritingDirection
from .resolved_pipeline import ResolvedFlexItem, compute_resolved_flex

@dataclass(frozen=True, slots=True)
class ResolvedTreeNode:
    node_id: str
    parent_id: str | None
    width: float
    height: float
    flex: FlexBasis | None = None
    direction: FlexDirection = FlexDirection.ROW
    wrap: FlexWrap = FlexWrap.NOWRAP
    main_gap: float = 0.0
    cross_gap: float = 0.0
    order: int = 0

def compute_resolved_tree(
    nodes: tuple[ResolvedTreeNode, ...],
    *,
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> LayoutResult:
    """Build absolute content/padding/border/margin boxes for zero-edge nodes.

    Root defines the containing extent. Every non-root item requires a
    pre-resolved FlexBasis. Child contexts are recomputed using the *flexed*
    size allocated by the parent (important for nested percent descendants).
    """
    if not isinstance(nodes, tuple) or any(not isinstance(n, ResolvedTreeNode) for n in nodes):
        raise TypeError("Expected tuple of ResolvedTreeNode.")
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be nonnegative.")
    if not nodes:
        return LayoutResult(1, generation, ())
    if nodes[0].parent_id is not None:
        raise SFLEError(DiagnosticCode.INVALID_TREE, "First node must be root.")
    by_id = {}
    children: dict[str, list[ResolvedTreeNode]] = {}
    for index, node in enumerate(nodes):
        if not node.node_id or node.node_id in by_id:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate/empty node ID.")
        if index and (node.parent_id is None or node.parent_id not in by_id):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Tree must be preorder.")
        if type(node.order) is not int:
            raise TypeError("order must be integer.")
        if not isinstance(node.direction, FlexDirection) or not isinstance(node.wrap, FlexWrap):
            raise TypeError("Invalid Flex direction or wrap.")
        # Force the existing pure kernel to validate dimensions even for leaves.
        from .flex_math import _number
        for value in (node.width, node.height, node.main_gap, node.cross_gap):
            if _number(value, "resolved geometry") < 0:
                raise ValueError("Resolved sizes/gaps must be nonnegative.")
        if index and not isinstance(node.flex, FlexBasis):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE, "Non-root needs pre-resolved FlexBasis.")
        by_id[node.node_id] = node
        children[node.node_id] = []
        if index:
            children[node.parent_id].append(node)
    geometry: dict[str, Rect] = {nodes[0].node_id: Rect(0, 0, nodes[0].width, nodes[0].height)}
    for node in nodes:
        origin = geometry[node.node_id]
        descendants = children[node.node_id]
        if not descendants:
            continue
        horizontal = node.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        flex_items = tuple(ResolvedFlexItem(
            child.node_id, child.flex,
            child.height if horizontal else child.width, child.order
        ) for child in descendants)
        placed = compute_resolved_flex(
            flex_items, origin.width, origin.height,
            direction=node.direction, writing=writing, wrap=node.wrap,
            main_gap=node.main_gap, cross_gap=node.cross_gap,
        )
        for item in placed.items:
            rect = item.rect
            geometry[item.node_id] = Rect(
                origin.x + rect.x, origin.y + rect.y, rect.width, rect.height
            )
    return LayoutResult(1, generation, tuple(
        (node.node_id, BoxRect(geometry[node.node_id], geometry[node.node_id],
                               geometry[node.node_id], geometry[node.node_id]))
        for node in nodes
    ))
