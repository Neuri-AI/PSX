"""Engine-neutral typed recursive geometry validation and dispatch."""
from __future__ import annotations

from psx.layout.contracts.model import WritingDirection
from psx.layout.contracts.recursive_tree import (
    AutoCrossSize, MarginTreeLayout, MarginTreeNode,
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
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer.")
    if not isinstance(writing, WritingDirection):
        raise TypeError("writing must be WritingDirection.")
    if not isinstance(nodes, tuple) or any(not isinstance(n, MarginTreeNode) for n in nodes):
        raise TypeError("nodes must be tuple[MarginTreeNode, ...].")

    compute = getattr(engine, "compute_recursive_tree", None)
    if not callable(compute):
        raise TypeError(
            "Recursive geometry requires an engine with compute_recursive_tree()."
        )
    return compute(
        nodes, generation=generation, writing=writing, auto_cross=auto_cross,
    )
