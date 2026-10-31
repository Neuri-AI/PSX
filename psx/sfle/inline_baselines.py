"""Native-measured inline baselines for semantic <span> participants.

Cinnamon's Flex baseline kernel needs an intrinsic baseline for every row
participant. A span is a structural formatting host, not a measured native
leaf: its baseline comes from its first text descendant, relative to the
span *content* box. The kernel adds the span's padding/border itself.
No toolkit widgets or geometry are mutated here.
"""
from __future__ import annotations

from dataclasses import replace

from psx.core.vnode import NodeKind
from .model import IntrinsicSizes, LayoutInput, MeasuredBox


def with_inline_span_baselines(
    snapshot: LayoutInput,
    identities: tuple[tuple[str, object], ...],
) -> LayoutInput:
    source = dict(identities)
    nodes = {node.node_id: node for node in snapshot.nodes}
    children: dict[str, list[str]] = {}
    for node in snapshot.nodes:
        if node.parent_id is not None:
            children.setdefault(node.parent_id, []).append(node.node_id)
    measurements = {item.node_id: item for item in snapshot.measurements}
    additional = []

    for parent in snapshot.nodes:
        if dict(parent.style).get("align_items") != "baseline":
            continue
        for identifier in children.get(parent.node_id, ()):
            origin = source.get(identifier)
            if (origin is None or origin.kind is not NodeKind.HOST
                    or origin.type not in ("span", "label")
                    or identifier in measurements):
                continue
            # A typical span has precisely one Text child; nested inline
            # spans inherit their first descendant's text baseline too.
            pending = list(reversed(children.get(identifier, ())))
            baseline = None
            while pending:
                child_id = pending.pop()
                item = measurements.get(child_id)
                if item is not None and item.intrinsic.baseline is not None:
                    baseline = item.intrinsic.baseline
                    break
                child = source.get(child_id)
                if child is not None and child.type in ("span", "label"):
                    pending.extend(reversed(children.get(child_id, ())))
            if baseline is None:
                # Never fabricate a font baseline from a widget's border.
                continue
            # Structural spans have no independent intrinsic sizing;
            # baseline metadata does not override their resolved contents.
            intrinsic = IntrinsicSizes(0, 0, 0, 0, 0, 0, baseline=baseline)
            additional.append(MeasuredBox(
                identifier, intrinsic, snapshot.constraints, snapshot.generation,
            ))
    if not additional:
        return snapshot
    return replace(snapshot, measurements=snapshot.measurements + tuple(additional))
