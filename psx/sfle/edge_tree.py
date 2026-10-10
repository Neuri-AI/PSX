"""Nested, edge-aware resolved Flex geometry.

All CSS lengths and intrinsic bases are resolved upstream. This stage
supports positive padding/borders at every depth and fixed nonnegative margins
through the existing edge pipeline; it does not synthesize unresolved sizes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .box_geometry import UsedBoxEdges, UsedEdges
from .edge_pipeline import ResolvedEdgeItem, compute_edge_layout
from .errors import DiagnosticCode, SFLEError
from .flex_math import FlexBasis, _number
from .line_layout import FlexDirection, FlexWrap
from .model import BoxRect, LayoutResult, Rect, WritingDirection


@dataclass(frozen=True, slots=True)
class EdgeTreeNode:
    node_id: str
    parent_id: str | None
    width: float
    height: float
    flex: FlexBasis | None = None
    edges: UsedBoxEdges = UsedBoxEdges()
    direction: FlexDirection = FlexDirection.ROW
    wrap: FlexWrap = FlexWrap.NOWRAP
    main_gap: float = 0.0
    cross_gap: float = 0.0
    order: int = 0


def _offset(rect: Rect, x: float, y: float) -> Rect:
    return Rect(rect.x + x, rect.y + y, rect.width, rect.height)


def _offset_box(box: BoxRect, x: float, y: float) -> BoxRect:
    return BoxRect(
        content=_offset(box.content, x, y),
        padding=_offset(box.padding, x, y),
        border=_offset(box.border, x, y),
        margin=_offset(box.margin, x, y),
    )


def compute_edge_tree(
    nodes: tuple[EdgeTreeNode, ...],
    *,
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> LayoutResult:
    """Compose per-container Flex distribution through true content boxes.

    width/height are definite *content* dimensions used as hypothetical cross
    sizes only. Main axis dimensions come from the flex basis and the parent's
    final allocation. Root edges are supported as physical enclosing boxes;
    the root is placed at border-box origin (0,0).

    Replaced sizing, automatic child cross sizes, unresolved percentages,
    intrinsic cycles and signed/auto margins are outside this supported slice.
    """
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be nonnegative.")
    if not isinstance(writing, WritingDirection):
        raise TypeError("writing must be WritingDirection.")
    if not isinstance(nodes, tuple) or not all(isinstance(n, EdgeTreeNode) for n in nodes):
        raise TypeError("Expected tuple[EdgeTreeNode, ...].")
    if not nodes:
        return LayoutResult(1, generation, ())
    children: dict[str, list[EdgeTreeNode]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node.edges, UsedBoxEdges):
            raise TypeError("edges must be UsedBoxEdges.")
        if not node.node_id or node.node_id in children:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate or empty node ID.")
        if (index == 0 and node.parent_id is not None) or (index and node.parent_id not in children):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Nodes must have a preorder parent.")
        if index and not isinstance(node.flex, FlexBasis):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unresolved child flex-basis.", node.node_id)
        if not isinstance(node.direction, FlexDirection) or not isinstance(node.wrap, FlexWrap) or type(node.order) is not int:
            raise TypeError("Invalid flex direction, wrap or order.")
        for v in (node.width, node.height, node.main_gap, node.cross_gap):
            if _number(v, "size or gap") < 0:
                raise ValueError("Negative size/gap.")
        if node.edges.margin != UsedEdges():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE, "This recursive slice requires zero outer margins.", node.node_id)
        children[node.node_id] = []
        if index:
            children[node.parent_id].append(node)
    root = nodes[0]
    e = root.edges
    border = Rect(0, 0, root.width + e.padding.horizontal + e.border.horizontal,
                  root.height + e.padding.vertical + e.border.vertical)
    padding = Rect(e.border.left, e.border.top,
                   root.width + e.padding.horizontal, root.height + e.padding.vertical)
    content = Rect(padding.x + e.padding.left, padding.y + e.padding.top, root.width, root.height)
    geometry: dict[str, BoxRect] = {root.node_id: BoxRect(content, padding, border, border)}
    for node in nodes:
        origin = geometry[node.node_id].content
        descendants = children[node.node_id]
        if not descendants:
            continue
        horizontal = node.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        items = tuple(ResolvedEdgeItem(
            child.node_id,
            child.flex,
            child.height if horizontal else child.width,
            child.edges,
            child.order,
        ) for child in descendants)
        layout = compute_edge_layout(
            items, origin.width, origin.height,
            direction=node.direction, writing=writing, wrap=node.wrap,
            main_gap=node.main_gap, cross_gap=node.cross_gap,
        )
        for node_id, box in layout.boxes:
            geometry[node_id] = _offset_box(box, origin.x, origin.y)
    return LayoutResult(1, generation, tuple(
        (node.node_id, geometry[node.node_id]) for node in nodes
    ))
