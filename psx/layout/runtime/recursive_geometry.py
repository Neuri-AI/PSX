"""Engine-neutral historical recursive geometry entry point.

Python and Rust consume identical immutable legacy data records. Python's
numerical code is imported only for an explicitly selected Python backend.
Rust uses only the compiled independent margin_tree/auto_cross_tree kernels.
"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum
import json

from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.contracts.model import Rect, WritingDirection
from psx.layout.contracts.recursive_tree import (
    AutoCrossSize, MarginFlexBox, MarginTreeLayout, MarginTreeNode,
)


def compute_margin_tree(
    nodes: tuple[MarginTreeNode, ...], *,
    generation: int,
    writing: WritingDirection = WritingDirection.LTR,
    engine: object | None = None,
    auto_cross: tuple[AutoCrossSize, ...] = (),
) -> MarginTreeLayout:
    """Compute the same historical geometry with the selected numerical engine."""
    if engine is None:
        from psx.layout.engine.backend import load_layout_engine
        engine = load_layout_engine()
    backend = getattr(engine, "backend_name", None)
    if backend == "python":
        if auto_cross:
            from psx.layout.fallback.auto_cross_tree import compute_auto_cross_tree
            return compute_auto_cross_tree(
                nodes, auto_cross=auto_cross, generation=generation,
                writing=writing,
            )
        from psx.layout.fallback.margin_tree import compute_margin_tree as python_compute
        return python_compute(nodes, generation=generation, writing=writing)
    if backend != "rust":
        raise TypeError("Recursive geometry requires Cinnamon Rust or Python engine.")

    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer.")
    if not isinstance(writing, WritingDirection):
        raise TypeError("writing must be WritingDirection.")
    if not isinstance(nodes, tuple) or any(not isinstance(n, MarginTreeNode) for n in nodes):
        raise TypeError("nodes must be tuple[MarginTreeNode, ...].")

    module = getattr(engine, "_module", None)
    native = getattr(module, "compute_recursive_tree_json", None)
    if not callable(native):
        raise SFLEError(
            DiagnosticCode.BACKEND_MISMATCH,
            "The selected Rust Cinnamon wheel lacks recursive geometry ABI.",
        )
    payload = {
        "generation": generation,
        "writing": writing.value,
        "nodes": [asdict(node) for node in nodes],
        "auto_cross": [item.node_id for item in auto_cross],
    }
    # Explicit serializer of enums preserves the original typed contract.
    def serialize(value: object):
        if isinstance(value, Enum):
            return value.value
        raise TypeError(f"Unsupported recursive wire value: {type(value).__name__}")

    try:
        wire = json.dumps(payload, default=serialize, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SFLEError(
            DiagnosticCode.INVALID_SNAPSHOT,
            f"Invalid recursive geometry snapshot: {exc}",
        ) from exc
    try:
        result = json.loads(native(wire))
    except (ValueError, TypeError) as exc:
        raise SFLEError(
            DiagnosticCode.INVALID_TREE,
            f"Native recursive geometry rejected the tree: {exc}",
        ) from exc
    if not isinstance(result, dict) or result.get("generation") != generation:
        raise SFLEError(
            DiagnosticCode.BACKEND_MISMATCH,
            "Rust recursive geometry returned an invalid generation.",
        )
    def rect(data):
        return Rect(data["x"], data["y"], data["width"], data["height"])

    # Fixed (non-auto) CSS margins are *inputs*, not computed layout sizes.
    # A serde_json float roundtrip can change the shortest binary rendering by
    # one ULP; the historical Python API preserves the exact supplied value.
    # Leave auto margins and every coordinate to the real native Rust solver.
    source_items = {
        node.node_id: node.item for node in nodes if node.item is not None
    }
    def used_margin(box, side):
        item = source_items.get(box["node_id"])
        if item is not None:
            declared = getattr(item, side).value
            if declared is not None:
                return declared
        return box["used_" + side + "_margin"]

    try:
        boxes = tuple(MarginFlexBox(
            box["node_id"], rect(box["content"]), rect(box["padding"]),
            rect(box["border"]), used_margin(box, "main_start"),
            used_margin(box, "main_end"), box["line_index"],
            box["used_cross_start_margin"], box["used_cross_end_margin"],
        ) for box in result["boxes"])
    except (TypeError, KeyError, ValueError) as exc:
        raise SFLEError(
            DiagnosticCode.BACKEND_MISMATCH,
            "Rust recursive geometry returned malformed rectangles.",
        ) from exc
    if tuple(b.node_id for b in boxes) != tuple(n.node_id for n in nodes):
        raise SFLEError(
            DiagnosticCode.BACKEND_MISMATCH,
            "Rust recursive geometry changed tree ordering or identities.",
        )
    return MarginTreeLayout(generation, boxes)
