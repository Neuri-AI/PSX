"""Recursive resolved Flex composition with the full existing margin/alignment kernel.

This is a CSS-resolved-input geometry stage. It cannot infer auto container
sizes, intrinsic metrics or percentage bases. Signed margins remain independent
used offsets: no fictitious nonnegative margin rectangle is created.
"""
from __future__ import annotations

from dataclasses import dataclass

from .align_content import AlignContent
from .box_geometry import UsedBoxEdges, UsedEdges
from .cross_alignment import CrossAlign
from .errors import DiagnosticCode, SFLEError
from .flex_math import _number
from .line_layout import FlexDirection, FlexWrap
from .main_alignment import JustifyContent
from .margin_flex_pipeline import MarginFlexBox, MarginFlexItem, compute_margin_flex_layout
from .model import Rect, WritingDirection


@dataclass(frozen=True, slots=True)
class MarginTreeNode:
    node_id: str
    parent_id: str | None
    width: float
    height: float
    item: MarginFlexItem | None = None
    edges: UsedBoxEdges = UsedBoxEdges()
    direction: FlexDirection = FlexDirection.ROW
    wrap: FlexWrap = FlexWrap.NOWRAP
    main_gap: float = 0.0
    cross_gap: float = 0.0
    justify: JustifyContent = JustifyContent.FLEX_START
    align_items: CrossAlign = CrossAlign.FLEX_START
    align_content: AlignContent = AlignContent.FLEX_START


@dataclass(frozen=True, slots=True)
class MarginTreeLayout:
    generation: int
    boxes: tuple[MarginFlexBox, ...]


def _translate(box: MarginFlexBox, x: float, y: float) -> MarginFlexBox:
    def move(r: Rect) -> Rect:
        return Rect(r.x + x, r.y + y, r.width, r.height)
    return MarginFlexBox(
        box.node_id, move(box.content), move(box.padding), move(box.border),
        box.used_main_start_margin, box.used_main_end_margin, box.line_index,
        box.used_cross_start_margin, box.used_cross_end_margin,
    )


def compute_margin_tree(
    nodes: tuple[MarginTreeNode, ...],
    *,
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> MarginTreeLayout:
    """Compose every child Flex context inside its parent's actual content box.

    Accepts signed/automatic main/cross margins, physical padding/border,
    justification and alignments supported by margin_flex_pipeline.
    Root has no parent, and its width/height are established content extents.
    """
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer.")
    if not isinstance(writing, WritingDirection):
        raise TypeError("writing must be WritingDirection.")
    if not isinstance(nodes, tuple) or any(not isinstance(n, MarginTreeNode) for n in nodes):
        raise TypeError("nodes must be tuple[MarginTreeNode, ...].")
    if not nodes:
        return MarginTreeLayout(generation, ())
    children: dict[str, list[MarginTreeNode]] = {}
    for index, node in enumerate(nodes):
        if not node.node_id or node.node_id in children:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate/empty node ID.")
        if index == 0:
            if node.parent_id is not None or node.item is not None:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Root cannot be a flex item.")
        elif node.parent_id not in children or node.item is None or node.item.node_id != node.node_id:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing parent or mismatched item.")
        if not isinstance(node.edges, UsedBoxEdges):
            raise TypeError("Expected UsedBoxEdges.")
        if index and node.edges != UsedBoxEdges():
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Child edges must be supplied through MarginFlexItem.edges.",
                node.node_id,
            )
        if node.edges.margin != UsedEdges():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE, "Container physical margins require item metadata.")
        for value in (node.width, node.height, node.main_gap, node.cross_gap):
            if _number(value, "resolved dimension") < 0:
                raise ValueError("Negative size or gap.")
        if not isinstance(node.direction, FlexDirection) or not isinstance(node.wrap, FlexWrap):
            raise TypeError("Invalid flex direction/wrap.")
        if not isinstance(node.justify, JustifyContent) or not isinstance(node.align_items, CrossAlign) or not isinstance(node.align_content, AlignContent):
            raise TypeError("Invalid flex alignment.")
        children[node.node_id] = []
        if index:
            children[node.parent_id].append(node)
    root = nodes[0]
    e = root.edges
    geometry: dict[str, MarginFlexBox] = {
        root.node_id: MarginFlexBox(
            root.node_id,
            Rect(e.border.left + e.padding.left, e.border.top + e.padding.top, root.width, root.height),
            Rect(e.border.left, e.border.top, root.width + e.padding.horizontal, root.height + e.padding.vertical),
            Rect(0, 0, root.width + e.padding.horizontal + e.border.horizontal, root.height + e.padding.vertical + e.border.vertical),
            0, 0, 0,
        ),
    }
    for parent in nodes:
        origin = geometry[parent.node_id].content
        items = tuple(child.item for child in children[parent.node_id])
        if not items:
            continue
        positioned = compute_margin_flex_layout(
            items, origin.width, origin.height,
            direction=parent.direction, writing=writing, wrap=parent.wrap,
            main_gap=parent.main_gap, cross_gap=parent.cross_gap,
            justify=parent.justify, align_items=parent.align_items,
            align_content=parent.align_content,
        )
        for box in positioned.boxes:
            geometry[box.node_id] = _translate(box, origin.x, origin.y)
    return MarginTreeLayout(generation, tuple(geometry[node.node_id] for node in nodes))
