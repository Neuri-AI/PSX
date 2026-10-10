"""F2.2.4 renderer-neutral recursive measurement dependency planning.

This stage does not guess CSS used child sizes. It traverses a validated
LayoutInput tree, distributes *explicit* child constraint snapshots, detects
missing/stale measurements and produces an immutable bottom-up worklist.
Only the UI-thread measurement adapter may fulfill the worklist.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .model import LayoutConstraints, LayoutInput, MeasuredBox


@dataclass(frozen=True, slots=True)
class MeasurementRequest:
    node_id: str
    constraints: LayoutConstraints
    generation: int
    revision: int


@dataclass(frozen=True, slots=True)
class MeasurementPlan:
    generation: int
    requests: tuple[MeasurementRequest, ...]
    reusable: tuple[MeasuredBox, ...]


def plan_measurements(
    snapshot: LayoutInput,
    *,
    child_constraints: tuple[tuple[str, LayoutConstraints], ...] = (),
    revisions: tuple[tuple[str, int], ...] = (),
) -> MeasurementPlan:
    """Plan a deterministic leaf-first measurement pass for a valid SFLE tree.

    Child constraints MUST come from a layout constraint computation stage.
    Inheriting a definite parent width for a child without CSS style/box
    resolution would be incorrect, therefore missing constraints fail closed.
    Reuse requires matching immutable constraints AND node revision.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("snapshot must be LayoutInput.")
    if not isinstance(child_constraints, tuple) or not isinstance(revisions, tuple):
        raise TypeError("Constraint and revision pairs must be tuples.")
    ids = {node.node_id for node in snapshot.nodes}
    supplied: dict[str, LayoutConstraints] = {}
    versions: dict[str, int] = {}
    for node_id, constraint in child_constraints:
        if not isinstance(node_id, str) or node_id not in ids or node_id in supplied:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Unknown/duplicate child constraint.")
        if not isinstance(constraint, LayoutConstraints):
            raise TypeError("Child constraints must be LayoutConstraints.")
        supplied[node_id] = constraint
    for node_id, revision in revisions:
        if not isinstance(node_id, str) or node_id not in ids or node_id in versions:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Unknown/duplicate revision.")
        if type(revision) is not int or revision < 0:
            raise ValueError("Revision must be a nonnegative integer.")
        versions[node_id] = revision
    if not snapshot.nodes:
        return MeasurementPlan(snapshot.generation, (), ())
    root = snapshot.nodes[0].node_id
    if root in supplied and supplied[root] != snapshot.constraints:
        raise SFLEError(DiagnosticCode.LAYOUT_CONSTRAINT, "Root constraints conflict.")
    known = {root: snapshot.constraints, **supplied}
    missing = ids.difference(known)
    if missing:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            f"Child constraints are not resolved: {sorted(missing)}.",
        )
    measured = {item.node_id: item for item in snapshot.measurements}
    # Validated LayoutInput is preorder. Reverse order is a child-before-parent
    # schedule, including sibling order without a recursive Python call stack.
    requests: list[MeasurementRequest] = []
    reusable: list[MeasuredBox] = []
    dirty_ancestors: set[str] = set()
    for node in reversed(snapshot.nodes):
        constraint = known[node.node_id]
        revision = versions.get(node.node_id, 0)
        previous = measured.get(node.node_id)
        if (node.node_id not in dirty_ancestors and previous is not None
                and previous.constraints == constraint and previous.revision == revision):
            reusable.append(previous)
        else:
            requests.append(MeasurementRequest(
                node.node_id, constraint, snapshot.generation, revision
            ))
            if node.parent_id is not None:
                dirty_ancestors.add(node.parent_id)
    return MeasurementPlan(snapshot.generation, tuple(requests), tuple(reusable))


def accept_measurement(
    request: MeasurementRequest, result: MeasuredBox, *, current_generation: int,
) -> MeasuredBox:
    """Reject stale native/UI-thread measurements before layout reuse."""
    if not isinstance(request, MeasurementRequest) or not isinstance(result, MeasuredBox):
        raise TypeError("Expected MeasurementRequest and MeasuredBox.")
    if type(current_generation) is not int or current_generation < 0:
        raise ValueError("current_generation must be nonnegative.")
    if request.generation != current_generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale measurement generation.")
    if (request.node_id != result.node_id or request.constraints != result.constraints
            or request.revision != result.revision):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Measurement snapshot mismatch.")
    return result
