"""Bottom-up intrinsic contribution for restricted nowrap Flex containers.

Supports row/column trees with definite leaf border-box contributions, fixed
edges, zero margins, and one automatic container cross axis. Results feed the
existing Flex geometry pass; they are NOT a general CSS intrinsic sizing engine.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .line_layout import FlexDirection, FlexWrap
from .margin_tree import MarginTreeNode, MarginTreeLayout, compute_margin_tree
from .model import WritingDirection


@dataclass(frozen=True, slots=True)
class AutoCrossSize:
    node_id: str


def compute_auto_cross_tree(
    nodes: tuple[MarginTreeNode, ...],
    *,
    auto_cross: tuple[AutoCrossSize, ...],
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> MarginTreeLayout:
    """Resolve auto cross sizes from child outer contributions, bottom up.

    Only non-wrapping, fixed-edge tree contributions are accepted. An auto-sized
    container must have a definite main size (supplied through the parent Flex
    item); flex grow/shrink and percent/cyclic sizing belong to later passes.
    """
    ids = {node.node_id for node in nodes}
    if len(ids) != len(nodes):
        raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate node IDs.")
    selected = [entry.node_id for entry in auto_cross]
    if len(selected) != len(set(selected)) or not set(selected).issubset(ids):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid auto cross declarations.")
    parents: dict[str, list[MarginTreeNode]] = {node.node_id: [] for node in nodes}
    for node in nodes:
        if node.parent_id is not None:
            if node.parent_id not in parents:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Non-preorder auto tree.")
            parents[node.parent_id].append(node)
    by_id = {node.node_id: node for node in nodes}
    for node in reversed(nodes):
        if node.node_id not in selected:
            continue
        if not parents[node.node_id] or node.wrap != FlexWrap.NOWRAP:
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto cross requires a nonempty nowrap container.")
        horizontal = node.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        contributions = []
        for child in parents[node.node_id]:
            item = by_id[child.node_id].item
            if item is None or item.cross_size_auto or item.cross_start.value is None or item.cross_end.value is None:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto cross requires definite child cross sizes and margins.")
            edge = item.edges
            cross_edges = (edge.padding.vertical + edge.border.vertical if horizontal
                           else edge.padding.horizontal + edge.border.horizontal)
            contributions.append(item.cross_content_size + cross_edges + item.cross_start.value + item.cross_end.value)
        used = max(0.0, *contributions)
        if node.parent_id is None:
            by_id[node.node_id] = replace(node, height=used) if horizontal else replace(node, width=used)
        else:
            item = node.item
            if item is None:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing container Flex item.")
            parent = by_id[node.parent_id]
            parent_horizontal = parent.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
            # Only propagate cross-size when parent and child cross axes match.
            if parent_horizontal != horizontal:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Orthogonal auto cross contribution requires distinct main-axis sizing.")
            updated_item = replace(item, cross_content_size=used)
            by_id[node.node_id] = replace(node, height=used, item=updated_item) if horizontal else replace(node, width=used, item=updated_item)
    return compute_margin_tree(tuple(by_id[node.node_id] for node in nodes), generation=generation, writing=writing)
