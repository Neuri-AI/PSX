"""Measured Block formatting for an explicitly bounded native layout snapshot.

A block root and its immediate measured native leaves are supported. Mixed
inline fragments and nested independent formatting contexts require their own
certified measurement protocols and are rejected rather than guessed.
"""
from __future__ import annotations

from .errors import DiagnosticCode, SFLECapabilityError
from .flow_layout import (
    BlockItem, InlineAtom, layout_block_children, layout_inline_atoms,
)
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
    mode = dict(root.style)
    display = mode.pop("display", "block")
    if mode:
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Block/Inline root has unresolved layout styles.",
        )
    if display not in ("block", "inline"):
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            f"Unsupported formatting context {display!r}.",
        )
    intrinsic_items = []
    for node in children:
        if node.component in ("div", "Flex", "Grid", "Scroll", "Box"):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Flow child {node.component!r} requires a nested formatter.",
            )
        if node.node_id not in measurements:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Native flow child {node.node_id!r} is missing intrinsic measurements.",
            )
        if dict(node.style):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Flow child {node.node_id!r} has unresolved layout styles.",
            )
        intrinsic_items.append(measurements[node.node_id].intrinsic)

    if display == "block":
        placements = layout_block_children(
            width,
            tuple(BlockItem(width, intrinsic.preferred_height)
                  for intrinsic in intrinsic_items),
        )
    else:
        placements = layout_inline_atoms(
            width,
            tuple(InlineAtom(
                intrinsic.preferred_width,
                intrinsic.preferred_height,
                intrinsic.baseline
                if intrinsic.baseline is not None
                else intrinsic.preferred_height,
            ) for intrinsic in intrinsic_items),
        )
    used_height = max(
        (placement.y + placement.height for placement in placements),
        default=0.0,
    )

    def box(rect: Rect) -> BoxRect:
        return BoxRect(rect, rect, rect, rect)

    # The mounted application root owns the complete native viewport. A
    # nested, independently auto-sized block requires a separate context.
    root_height = (
        snapshot.constraints.height.value
        if snapshot.constraints.height.definite
        else used_height
    )
    results = [(root.node_id, box(Rect(0.0, 0.0, width, root_height)))]
    results.extend(
        (node.node_id, box(Rect(item.x, item.y, item.width, item.height)))
        for node, item in zip(children, placements)
    )
    return LayoutResult(snapshot.schema_version, snapshot.generation, tuple(results))
