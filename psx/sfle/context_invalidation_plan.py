"""Conservative context-level invalidation planning for Cinnamon snapshots.

A plan describes dependencies; it does not authorize partial geometry reuse.
The solver must prove that unchanged contexts retain identical constraints
before selectively reusing their boxes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import LayoutInput


@dataclass(frozen=True, slots=True)
class ContextPlan:
    full_recompute: bool
    dirty_nodes: frozenset[str]
    directly_dirty_contexts: frozenset[str]
    reason: str


def plan_context_invalidation(
    previous: LayoutInput | None,
    current: LayoutInput,
) -> ContextPlan:
    """Find explicitly changed contexts without capturing native objects."""
    full = lambda reason: ContextPlan(True, frozenset(), frozenset(), reason)
    if previous is None:
        return full("no_previous_snapshot")
    if (previous.schema_version != current.schema_version
            or previous.constraints != current.constraints
            or previous.direction != current.direction):
        return full("environment_changed")
    old_nodes, new_nodes = previous.nodes, current.nodes
    if len(old_nodes) != len(new_nodes):
        return full("structure_changed")
    parent = {}
    dirty = set()
    flex = set()
    for old, new in zip(old_nodes, new_nodes):
        if (old.node_id, old.parent_id, old.component) != (
                new.node_id, new.parent_id, new.component):
            return full("structure_changed")
        parent[new.node_id] = new.parent_id
        if new.component == "Flex":
            flex.add(new.node_id)
        if old.style != new.style:
            dirty.add(new.node_id)
    old_measurements = {m.node_id: m for m in previous.measurements}
    new_measurements = {m.node_id: m for m in current.measurements}
    if old_measurements.keys() != new_measurements.keys():
        return full("measurement_set_changed")
    for node_id, new in new_measurements.items():
        old = old_measurements[node_id]
        # A revision update alone may be a font/DPI/resource invalidation.
        if (old.intrinsic != new.intrinsic or
                old.constraints != new.constraints or
                old.revision != new.revision):
            dirty.add(node_id)
    from .layout_change_effects import affected_flex_contexts
    affected = affected_flex_contexts(
        frozenset(dirty), parent_by_id=parent,
        flex_node_ids=frozenset(flex),
    )
    if affected is None:
        return full("invalid_dependency_graph")
    return ContextPlan(False, frozenset(dirty), affected, "scoped_dependencies")
