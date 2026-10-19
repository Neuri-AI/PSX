"""Renderer-neutral Cinnamon Block/Inline geometry over native measurements.

Only explicit semantic flow hosts participate. All text widths, line heights
and baselines arrive from renderer-native intrinsic ports. Block descendants
stack in normal flow; consecutive inline descendants form measured lines, and
their stable per-host rectangles are unions of the actual native fragments.
Unsupported widths, CSS styles and anonymous layout contexts fail closed.
"""
from __future__ import annotations

from collections import defaultdict

from psx.markup.html_aliases import FORMATTING_TAGS
from .errors import DiagnosticCode, SFLECapabilityError
from .flow_layout import (
    BlockPlacement, InlineAtom, layout_inline_atoms,
)
from .model import BoxRect, LayoutInput, LayoutResult, Rect


def compute_measured_block_snapshot(snapshot: LayoutInput) -> LayoutResult:
    """Layout a bounded Block/Inline tree, retaining exact VNode identities."""
    if not snapshot.nodes or snapshot.nodes[0].component not in FORMATTING_TAGS:
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Measured flow formatting requires a semantic Block/Inline root.",
        )
    width = snapshot.constraints.width.value
    if width is None or not snapshot.constraints.width.definite:
        raise SFLECapabilityError(
            DiagnosticCode.LAYOUT_CONSTRAINT,
            "Measured flow formatting requires a definite containing width.",
        )
    root = snapshot.nodes[0]
    if root.parent_id is not None:
        raise SFLECapabilityError(
            DiagnosticCode.INVALID_TREE, "Flow root must have no parent.",
        )
    tree = {node.node_id: node for node in snapshot.nodes}
    children = defaultdict(list)
    for node in snapshot.nodes[1:]:
        children[node.parent_id].append(node)
    metrics = {item.node_id: item.intrinsic for item in snapshot.measurements}
    geometry: dict[str, Rect] = {}

    def display(node) -> str | None:
        if node.component not in FORMATTING_TAGS:
            return None
        style = dict(node.style)
        from psx.sfle.display_context import resolve_display, InnerDisplay
        selected = style.pop("display", None)
        mode = resolve_display(node.component, selected)
        if mode.inner is not InnerDisplay.FLOW or style:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"{node.component} requires a supported Block/Inline flow style.",
                node.node_id,
            )
        return mode.outer.value

    def leaf(node):
        if node.node_id not in metrics:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Native flow child {node.node_id!r} is missing intrinsic measurements.",
                node.node_id,
            )
        if dict(node.style):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Flow child {node.node_id!r} has unresolved layout styles.",
                node.node_id,
            )
        if children[node.node_id]:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Nested Block/Inline formatting for native child {node.node_id!r} "
                "requires an explicit nested format adapter.",
                node.node_id,
            )
        return metrics[node.node_id]

    def inline_run(nodes, x: float, y: float, available: float) -> float:
        atoms = []
        owners = []
        fragments = []

        def collect(node):
            mode = display(node)
            if mode is None:
                intrinsic = leaf(node)
                baseline = (intrinsic.baseline
                            if intrinsic.baseline is not None
                            else intrinsic.preferred_height)
                atoms.append(InlineAtom(
                    intrinsic.preferred_width, intrinsic.preferred_height,
                    baseline,
                ))
                fragments.append(node)
                return
            if mode != "inline":
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Block children cannot participate inside an Inline formatting run.",
                    node.node_id,
                )
            owners.append(node)
            for sub in children[node.node_id]:
                collect(sub)

        for node in nodes:
            collect(node)
        placements = layout_inline_atoms(available, tuple(atoms))
        for node, place in zip(fragments, placements):
            geometry[node.node_id] = Rect(
                x + place.x, y + place.y, place.width, place.height,
            )
        for owner in reversed(owners):
            descendants = [geometry[child.node_id]
                           for child in children[owner.node_id]
                           if child.node_id in geometry]
            if not descendants:
                geometry[owner.node_id] = Rect(x, y, 0, 0)
                continue
            left = min(box.x for box in descendants)
            top = min(box.y for box in descendants)
            right = max(box.x + box.width for box in descendants)
            bottom = max(box.y + box.height for box in descendants)
            geometry[owner.node_id] = Rect(
                left, top, right - left, bottom - top,
            )
        return max((place.y + place.height for place in placements), default=0.0)

    def block_node(node, x: float, y: float, available: float) -> float:
        mode = display(node)
        if mode is None:
            intrinsic = leaf(node)
            geometry[node.node_id] = Rect(
                x, y, available, intrinsic.preferred_height,
            )
            return intrinsic.preferred_height
        if mode == "inline":
            return inline_run((node,), x, y, available)
        cursor = 0.0
        pending = []

        def flush() -> None:
            nonlocal cursor
            if pending:
                cursor += inline_run(tuple(pending), x, y + cursor, available)
                pending.clear()

        for child in children[node.node_id]:
            if display(child) == "inline":
                pending.append(child)
            else:
                flush()
                cursor += block_node(child, x, y + cursor, available)
        flush()
        geometry[node.node_id] = Rect(x, y, available, cursor)
        return cursor

    if display(root) == "inline":
        content_height = inline_run(
            tuple(children[root.node_id]), 0.0, 0.0, width,
        )
    else:
        content_height = block_node(root, 0.0, 0.0, width)
    root_height = (
        snapshot.constraints.height.value
        if snapshot.constraints.height.definite
        else content_height
    )
    geometry[root.node_id] = Rect(0.0, 0.0, width, root_height)

    def box(rect: Rect) -> BoxRect:
        return BoxRect(rect, rect, rect, rect)

    result = tuple((node.node_id, box(geometry[node.node_id]))
                   for node in snapshot.nodes)
    return LayoutResult(snapshot.schema_version, snapshot.generation, result)
