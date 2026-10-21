"""Conservative C5 layout dependency closure.

This module identifies the nodes potentially affected by an intrinsic change.
A full Flex line may redistribute siblings, so any affected container's
children are conservatively included; unrelated branches below a disjoint
container are excluded unless their ancestor box can itself resize.

This is a dependency *plan*, not a substitute for SFLE's pure layout solver.
"""
from __future__ import annotations

from dataclasses import dataclass

from psx.sfle.model import LayoutInput


@dataclass(frozen=True, slots=True)
class DependencyClosure:
    dirty: frozenset[str]
    ancestors: frozenset[str]
    layout_candidates: frozenset[str]


def plan_layout_dependents(snapshot: LayoutInput, dirty: frozenset[str]) -> DependencyClosure:
    parents = {node.node_id: node.parent_id for node in snapshot.nodes}
    if len(parents) != len(snapshot.nodes):
        raise ValueError("Duplicate node identity in dependency snapshot.")
    for node_id, parent in parents.items():
        if parent is not None and parent not in parents:
            raise ValueError(f"Missing layout parent {parent!r} for {node_id!r}.")
    children: dict[str, set[str]] = {node_id: set() for node_id in parents}
    for node_id, parent in parents.items():
        if parent is not None:
            children[parent].add(node_id)
    unknown = dirty - parents.keys()
    if unknown:
        raise ValueError(f"Unknown dirty layout nodes: {sorted(unknown)!r}")

    ancestors: set[str] = set()
    candidates: set[str] = set(dirty)
    for node_id in dirty:
        parent = parents[node_id]
        seen = {node_id}
        while parent is not None:
            if parent in seen:
                raise ValueError("Cyclic layout dependency graph.")
            seen.add(parent)
            ancestors.add(parent)
            parent = parents[parent]
    candidates.update(ancestors)

    # Every sibling in an affected flex container may move/shrink/grow.
    for parent in ancestors:
        candidates.update(children[parent])

    return DependencyClosure(dirty, frozenset(ancestors), frozenset(candidates))
