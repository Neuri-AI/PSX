"""Preserve a replaced Image's native aspect ratio when CSS sets only one axis.

CSS width/height are geometry declarations, not a request to squash an
image's unmodified intrinsic height/width. All native image adapters provide
decoded resource dimensions via the same measured intrinsic contract.
Cinnamon accepts an immutable aspect_ratio hint and resolves the opposite
auto axis after flex sizing (including responsive %, vw and vh lengths).
"""
from __future__ import annotations

from dataclasses import replace
import math

from .lengths import LengthKind, parse_length
from .model import LayoutInput


def with_replaced_image_aspect_ratios(snapshot: LayoutInput) -> LayoutInput:
    """Annotate only single-axis-sized Image leaves with native proportions.

    Do not override an explicit aspect_ratio or a second authored dimension.
    Do not infer geometry from cached widget allocations or renderer defaults.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("Expected an immutable Cinnamon layout snapshot.")
    metrics = {measurement.node_id: measurement.intrinsic
               for measurement in snapshot.measurements}
    updated = []
    changed = False

    for node in snapshot.nodes:
        if node.component != "Image":
            updated.append(node)
            continue
        style = dict(node.style)
        if "aspect_ratio" in style:
            updated.append(node)
            continue

        def declared(axis: str) -> bool:
            value = style.get("layout_" + axis, style.get(axis, "auto"))
            return parse_length(value).kind is not LengthKind.AUTO

        if declared("width") == declared("height"):
            updated.append(node)
            continue
        native = metrics.get(node.node_id)
        if native is None:
            updated.append(node)
            continue
        width, height = native.preferred_width, native.preferred_height
        if (width <= 0 or height <= 0
                or not math.isfinite(width) or not math.isfinite(height)):
            updated.append(node)
            continue
        style["aspect_ratio"] = width / height
        updated.append(replace(node, style=tuple(sorted(style.items()))))
        changed = True

    return replace(snapshot, nodes=tuple(updated)) if changed else snapshot
