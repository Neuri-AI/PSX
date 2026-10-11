"""F2.2.4.5 pure dependency-driven remeasurement invalidation.

Compare two resolved-size tree snapshots and identify the affected nodes.
The coordinator must schedule UI-thread measurement separately. This module
does not solve automatic/cyclic CSS sizes or execute native measurement.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .model import LayoutInput
from .used_size_tree import UsedSizeTree


@dataclass(frozen=True, slots=True)
class RemeasurementDelta:
    generation: int
    changed: tuple[str, ...]
    remeasure: tuple[str, ...]
    deferred: tuple[str, ...]


def plan_remeasurement(
    snapshot: LayoutInput, previous: UsedSizeTree, current: UsedSizeTree
) -> RemeasurementDelta:
    """Invalidate changed constraints, their descendants, and their ancestors.

    CSS constraints changed on a node may affect every descendant, while
    changed intrinsic measurements invalidate ancestors. Nodes with unresolved
    axes remain deferred rather than being treated as definite zero.
    Input snapshots must refer to the exact same node set and generation.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(previous, UsedSizeTree) or not isinstance(current, UsedSizeTree):
        raise TypeError("Expected LayoutInput and two UsedSizeTree snapshots.")
    if previous.generation > current.generation or current.generation != snapshot.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale or mismatched used-size generation.")
    ids = tuple(node.node_id for node in snapshot.nodes)
    def checked(tree: UsedSizeTree):
        keys = tuple(node_id for node_id, _ in tree.content)
        if keys != ids:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Used-size tree does not match layout node ordering.")
        return dict(tree.content)
    old, new = checked(previous), checked(current)
    changed = {node_id for node_id in ids if old[node_id] != new[node_id]}
    affected = set(changed)
    parents = {node.node_id: node.parent_id for node in snapshot.nodes}
    # Both dependent descendants and intrinsic-size-dependent ancestors may
    # require measurement after a constraint change.
    for node in snapshot.nodes:
        if node.parent_id in affected:
            affected.add(node.node_id)
    for node_id in tuple(affected):
        parent = parents[node_id]
        while parent is not None:
            affected.add(parent)
            parent = parents[parent]
    deferred = tuple(node_id for node_id in ids if (
        not new[node_id].width.definite or not new[node_id].height.definite
    ))
    return RemeasurementDelta(
        current.generation,
        tuple(node_id for node_id in ids if node_id in changed),
        tuple(node_id for node_id in reversed(ids) if node_id in affected),
        deferred,
    )
