"""F2.2.4 integration of resolved recursive Flex geometry and UI measurements.

A geometry pass supplies established parent content boxes. The measurement
worklist uses those boxes rather than available-space hints, and delegates to
an explicit native UI-thread measurement port. This is a *resolved geometry*
bridge, not a solver for indefinite CSS auto dimensions or percentage cycles.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constraint_propagation import ChildSizing, plan_styled_measurements
from .errors import DiagnosticCode, SFLEError
from .margin_tree import MarginTreeLayout, MarginTreeNode, compute_margin_tree
from .measurement_round import MeasurementRound
from .model import AvailableSize, LayoutConstraints, LayoutInput, MeasuredBox, WritingDirection
from .native_measurement import NativeMeasurementPort, fulfill_native_round


@dataclass(frozen=True, slots=True)
class RecursiveMeasurementResult:
    geometry: MarginTreeLayout
    measurements: tuple[MeasuredBox, ...]
    deferred: tuple[str, ...]


def measure_resolved_margin_tree(
    snapshot: LayoutInput,
    nodes: tuple[MarginTreeNode, ...],
    *,
    child_sizing: tuple[tuple[str, ChildSizing], ...],
    revisions: tuple[tuple[str, int], ...] = (),
    port: NativeMeasurementPort,
    current_generation: int,
) -> RecursiveMeasurementResult:
    """Compute resolved boxes and measure dependent children on the UI thread.

    Exact node ordering and generation are verified before touching widgets.
    Cached measurements may only be reused when both revision and constraints
    still match, subject to conservative ancestor invalidation in the planner.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("snapshot must be LayoutInput.")
    if not isinstance(port, NativeMeasurementPort):
        raise TypeError("port must be NativeMeasurementPort.")
    if snapshot.generation != current_generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale recursive measurement generation.")
    if tuple(node.node_id for node in snapshot.nodes) != tuple(node.node_id for node in nodes):
        raise SFLEError(DiagnosticCode.INVALID_TREE, "Geometry and measurement trees disagree.")
    if any(a.parent_id != b.parent_id for a, b in zip(snapshot.nodes, nodes)):
        raise SFLEError(DiagnosticCode.INVALID_TREE, "Geometry parent references disagree.")
    geometry = compute_margin_tree(nodes, generation=current_generation, writing=snapshot.direction)
    parent_content = tuple((
        box.node_id,
        LayoutConstraints(
            AvailableSize(box.content.width, True),
            AvailableSize(box.content.height, True),
        ),
    ) for box in geometry.boxes)
    plan = plan_styled_measurements(
        snapshot, parent_content=parent_content,
        child_sizing=child_sizing, revisions=revisions,
    )
    constraints = {
        node_id: value for node_id, value in (
            (snapshot.nodes[0].node_id, snapshot.constraints),
            *(
                (entry.node_id, entry.constraints) for entry in plan.requests
            ),
            *((entry.node_id, entry.constraints) for entry in plan.reusable),
        )
    } if snapshot.nodes else {}
    deferred = tuple(
        node.node_id for node in snapshot.nodes
        if not constraints[node.node_id].width.definite
        or not constraints[node.node_id].height.definite
    )
    round_ = MeasurementRound(current_generation, plan.requests, plan.reusable, deferred)
    measurements = fulfill_native_round(round_, port, current_generation=current_generation)
    return RecursiveMeasurementResult(geometry, measurements, deferred)
