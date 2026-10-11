"""Intrinsic leaf sizing inputs for recursive Flex layout.

This stage converts *measured* intrinsic values into CSS flex-basis and cross
size suggestions. The Flex kernel still computes final used item geometry,
including grow/shrink, min/max and stretch. A leaf has no descendant sizing
dependency, so this stage does not speculate about container auto sizes.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import DiagnosticCode, SFLEError
from .intrinsic import IntrinsicFlexInput, MainAxis
from .lengths import Length
from .line_layout import FlexDirection
from .margin_tree import MarginTreeNode, MarginTreeLayout, compute_margin_tree
from .model import MeasuredBox, WritingDirection


@dataclass(frozen=True, slots=True)
class IntrinsicLeafStyle:
    node_id: str
    flex_basis: Length
    main_size: float | None = None
    min_main_size: float | None = None
    max_main_size: float | None = None
    cross_size_auto: bool = True


def prepare_measured_leaf_nodes(
    nodes: tuple[MarginTreeNode, ...],
    *,
    measurements: tuple[MeasuredBox, ...],
    leaves: tuple[IntrinsicLeafStyle, ...],
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> tuple[MarginTreeNode, ...]:
    """Resolve CSS content-driven leaf inputs, then distribute with Flex.

    Styles for non-leaf containers or missing intrinsic data fail closed.
    Revision/generation validation is upstream: measurement snapshots must be
    accepted by the native round protocol before calling this pure stage.
    """
    ids = [node.node_id for node in nodes]
    if len(ids) != len(set(ids)):
        raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate tree identifiers.")
    known = set(ids)
    parent_ids = {node.parent_id for node in nodes if node.parent_id is not None}
    by_node = {}
    for entry in measurements:
        if entry.node_id in by_node or entry.node_id not in known:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Duplicate or unknown measurement.")
        by_node[entry.node_id] = entry
    declared = {}
    for leaf in leaves:
        if not isinstance(leaf, IntrinsicLeafStyle):
            raise TypeError("Expected IntrinsicLeafStyle.")
        if leaf.node_id in declared or leaf.node_id not in known or leaf.node_id in parent_ids:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Intrinsic leaf must be unique and childless.")
        if leaf.node_id not in by_node:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Missing accepted leaf measurement.")
        declared[leaf.node_id] = leaf
    adapted = []
    directions = {}
    for node in nodes:
        if node.parent_id is not None:
            parent = next((candidate for candidate in nodes if candidate.node_id == node.parent_id), None)
            if parent is None:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Unknown intrinsic leaf parent.")
            directions[node.node_id] = (
                MainAxis.HORIZONTAL
                if parent.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
                else MainAxis.VERTICAL
            )
        style = declared.get(node.node_id)
        if style is None:
            adapted.append(node)
            continue
        if node.item is None or node.intrinsic_basis is not None:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Conflicting intrinsic item declaration.")
        metric = by_node[node.node_id].intrinsic
        axis = directions[node.node_id]
        preferred_cross = (
            metric.preferred_height if axis == MainAxis.HORIZONTAL
            else metric.preferred_width
        )
        adapted.append(replace(
            node,
            item=replace(
                node.item, cross_content_size=(
                    preferred_cross if style.cross_size_auto
                    else node.item.cross_content_size
                ),
                cross_size_auto=style.cross_size_auto,
            ),
            intrinsic_basis=IntrinsicFlexInput(
                intrinsic=metric, axis=axis,
                flex_basis=style.flex_basis,
                grow=node.item.flex.grow, shrink=node.item.flex.shrink,
                preferred_main_size=style.main_size,
                min_main_size=style.min_main_size,
                max_main_size=style.max_main_size,
            ),
        ))
    return tuple(adapted)


def compute_measured_leaf_tree(
    nodes: tuple[MarginTreeNode, ...], *,
    measurements: tuple[MeasuredBox, ...],
    leaves: tuple[IntrinsicLeafStyle, ...],
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
) -> MarginTreeLayout:
    """Compute final used geometry after preparing measured intrinsic leaves."""
    prepared = prepare_measured_leaf_nodes(
        nodes, measurements=measurements, leaves=leaves,
        generation=generation, writing=writing,
    )
    return compute_margin_tree(prepared, generation=generation, writing=writing)
