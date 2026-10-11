"""Bottom-up intrinsic cross contributions for recursive Flex containers."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .fixed_point import LayoutUnit
from .flex_math import FlexBasis
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
    """Resolve auto cross sizes from wrapped child lines, bottom up."""
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
        if not parents[node.node_id]:
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto cross requires a nonempty container.")
        horizontal = node.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        main_limit = LayoutUnit.from_nearest(node.width if horizontal else node.height)
        lines: list[tuple[LayoutUnit, LayoutUnit]] = []
        line_main = LayoutUnit.from_raw(0)
        line_cross = LayoutUnit.from_raw(0)
        for child in parents[node.node_id]:
            item = by_id[child.node_id].item
            if (item is None or item.cross_size_auto or item.cross_start.value is None
                    or item.cross_end.value is None or item.main_start.value is None
                    or item.main_end.value is None):
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto cross requires resolved child sizes and margins.")
            edge = item.edges
            cross_values = ((edge.padding.top, edge.padding.bottom, edge.border.top, edge.border.bottom)
                            if horizontal else
                            (edge.padding.left, edge.padding.right, edge.border.left, edge.border.right))
            main_values = ((edge.padding.left, edge.padding.right, edge.border.left, edge.border.right)
                           if horizontal else
                           (edge.padding.top, edge.padding.bottom, edge.border.top, edge.border.bottom))
            outer_main = LayoutUnit.from_nearest(item.flex.hypothetical)
            for value in (*main_values, item.main_start.value, item.main_end.value):
                outer_main += LayoutUnit.from_nearest(value)
            outer_cross = LayoutUnit.from_nearest(item.cross_content_size)
            for value in (*cross_values, item.cross_start.value, item.cross_end.value):
                outer_cross += LayoutUnit.from_nearest(value)
            separator = LayoutUnit.from_nearest(node.main_gap) if line_main.raw else LayoutUnit.from_raw(0)
            candidate = line_main + separator + outer_main
            if (node.wrap != FlexWrap.NOWRAP and line_main.raw
                    and candidate.raw > main_limit.raw):
                lines.append((line_main, line_cross))
                line_main, line_cross = outer_main, outer_cross
            else:
                line_main = candidate
                if outer_cross.raw > line_cross.raw:
                    line_cross = outer_cross
        lines.append((line_main, line_cross))
        used_u = LayoutUnit.from_raw(0)
        for index, (_, cross) in enumerate(lines):
            if index:
                used_u += LayoutUnit.from_nearest(node.cross_gap)
            used_u += cross
        used = used_u.to_px()
        if node.parent_id is None:
            by_id[node.node_id] = replace(node, height=used) if horizontal else replace(node, width=used)
        else:
            item = node.item
            if item is None:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing container Flex item.")
            parent = by_id[node.parent_id]
            parent_horizontal = parent.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
            auto_width = not horizontal
            parent_cross_width = not parent_horizontal
            if auto_width == parent_cross_width:
                updated_item = replace(item, cross_content_size=used, cross_size_auto=False)
            else:
                flex = item.flex
                hypothetical = max(flex.min_size, used)
                if flex.max_size is not None:
                    hypothetical = min(hypothetical, flex.max_size)
                updated_item = replace(item, flex=FlexBasis(
                    basis=used, hypothetical=hypothetical, grow=flex.grow,
                    shrink=flex.shrink, min_size=flex.min_size, max_size=flex.max_size,
                ))
            by_id[node.node_id] = replace(node, height=used, item=updated_item) if horizontal else replace(node, width=used, item=updated_item)
    return compute_margin_tree(tuple(by_id[node.node_id] for node in nodes), generation=generation, writing=writing)
