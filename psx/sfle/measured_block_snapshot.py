"""Measured Block formatting for an explicitly bounded native layout snapshot.

A block root and its immediate measured native leaves are supported. Mixed
inline fragments and nested independent formatting contexts require their own
certified measurement protocols and are rejected rather than guessed.
"""
from __future__ import annotations

from .errors import DiagnosticCode, SFLECapabilityError
from .flow_layout import BlockItem, layout_block_children
from .model import BoxRect, LayoutInput, LayoutResult, Rect


def compute_measured_block_snapshot(snapshot: LayoutInput) -> LayoutResult:
    if not snapshot.nodes or snapshot.nodes[0].component != "div":
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Measured block formatting requires a div root.",
        )
    width = snapshot.constraints.width.value
    if width is None or not snapshot.constraints.width.definite:
        raise SFLECapabilityError(
            DiagnosticCode.LAYOUT_CONSTRAINT,
            "Measured block formatting requires a definite containing width.",
        )
    root = snapshot.nodes[0]
    if root.parent_id is not None:
        raise SFLECapabilityError(DiagnosticCode.INVALID_TREE, "Block root must have no parent.")
    measurements = {measurement.node_id: measurement for measurement in snapshot.measurements}
    children = snapshot.nodes[1:]
    if any(node.parent_id != root.node_id for node in children):
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Nested Block/Inline formatting is not certified.",
        )
    items = []
    for node in children:
        if node.component in ("div", "Flex", "Grid", "Scroll", "Box"):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Block formatting child {node.component!r} needs a nested formatter.",
            )
        if node.node_id not in measurements:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Native block child {node.node_id!r} is missing intrinsic measurements.",
            )
        style = dict(node.style)
        if style:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Block child {node.node_id!r} has unresolved layout styles.",
            )
        intrinsic = measurements[node.node_id].intrinsic
        items.append(BlockItem(width, intrinsic.preferred_height))
    if dict(root.style):
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Block root layout styles are not yet part of the measured block subset.",
        )
    placements = layout_block_children(width, tuple(items))
    used_height = max(
        (placement.y + placement.height for placement in placements),
        default=0.0,
    )

    def box(rect: Rect) -> BoxRect:
        return BoxRect(rect, rect, rect, rect)

    results = [(root.node_id, box(Rect(0.0, 0.0, width, used_height)))]
    results.extend(
        (node.node_id, box(Rect(item.x, item.y, item.width, item.height)))
        for node, item in zip(children, placements)
    )
    return LayoutResult(snapshot.schema_version, snapshot.generation, tuple(results))
