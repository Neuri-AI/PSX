"""Integrated, bounded F2.2.4 measurement and recursive geometry pipeline.

The initial resolved geometry supplies per-node constraints. Measurements are
accepted atomically; intrinsic leaf bases and definite nowrap automatic cross
containers then produce used geometry. A second measurement pass observes the
actual allocated content-box widths. Unsupported CSS cycles remain fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .auto_cross_tree import AutoCrossSize, compute_auto_cross_tree
from .constraint_propagation import ChildSizing
from .errors import DiagnosticCode, SFLEError
from .intrinsic_tree import IntrinsicLeafStyle, prepare_measured_leaf_nodes
from .lengths import LengthKind
from .margin_tree import MarginTreeNode, compute_margin_tree
from .model import LayoutInput, AvailableSize, LayoutConstraints
from .native_measurement import NativeMeasurementPort
from .recursive_measurement import RecursiveMeasurementResult, measure_resolved_margin_tree


def _used_sizing(result: RecursiveMeasurementResult, nodes: tuple[MarginTreeNode, ...]) -> tuple[tuple[str, ChildSizing], ...]:
    from .lengths import Length
    boxes = {box.node_id: box.content for box in result.geometry.boxes}
    return tuple((node.node_id, ChildSizing(
        Length.px(boxes[node.node_id].width),
        Length.px(boxes[node.node_id].height),
    )) for node in nodes[1:])


def compute_recursive_pipeline(
    snapshot: LayoutInput,
    nodes: tuple[MarginTreeNode, ...],
    *,
    child_sizing: tuple[tuple[str, ChildSizing], ...],
    native_port: NativeMeasurementPort,
    intrinsic_leaves: tuple[IntrinsicLeafStyle, ...] = (),
    auto_cross: tuple[AutoCrossSize, ...] = (),
    revisions: tuple[tuple[str, int], ...] = (),
    current_generation: int,
    max_iterations: int = 8,
) -> RecursiveMeasurementResult:
    """Run measurement, intrinsic Flex distribution and final remeasurement.

    First-round intrinsic snapshots must match original CSS constraints.
    Final measurements use actual used content widths/heights to support
    height-for-width text measurement without treating preferred sizes as
    final used dimensions. The returned geometry remains generation-scoped.
    """
    first = measure_resolved_margin_tree(
        snapshot, nodes, child_sizing=child_sizing, revisions=revisions,
        port=native_port, current_generation=current_generation,
    )
    # A definite final box must not be fabricated from an unresolved CSS
    # percentage or an unrelated auto dimension. Only explicit intrinsic
    # leaf and restricted auto cross contexts may proceed through this solver.
    permitted = {entry.node_id for entry in intrinsic_leaves}
    permitted.update(entry.node_id for entry in auto_cross)
    styles = dict(child_sizing)
    for node_id in first.deferred:
        style = styles.get(node_id)
        if node_id not in permitted or style is None:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"No sizing rule for deferred CSS node {node_id!r}.",
            )
        if style.width.kind == LengthKind.PERCENT or style.height.kind == LengthKind.PERCENT:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Unresolved percentage dependency for {node_id!r}.",
            )
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer.")
    current = first
    seen: set[tuple[tuple[str, object], ...]] = set()
    for _ in range(max_iterations):
        prepared = prepare_measured_leaf_nodes(
            nodes, measurements=current.measurements, leaves=intrinsic_leaves,
            generation=current_generation, writing=snapshot.direction,
        )
        if auto_cross:
            sized = compute_auto_cross_tree(
                prepared, auto_cross=auto_cross,
                generation=current_generation, writing=snapshot.direction,
            )
        else:
            sized = compute_margin_tree(
                prepared, generation=current_generation, writing=snapshot.direction,
            )
        provisional = RecursiveMeasurementResult(sized, current.measurements, ())
        next_round = measure_resolved_margin_tree(
            replace(snapshot, measurements=current.measurements),
            prepared, child_sizing=_used_sizing(provisional, nodes),
            revisions=revisions, port=native_port,
            current_generation=current_generation,
        )
        previous_metrics = {m.node_id: m.intrinsic for m in current.measurements}
        new_metrics = {m.node_id: m.intrinsic for m in next_round.measurements}
        if previous_metrics == new_metrics:
            return RecursiveMeasurementResult(sized, next_round.measurements, next_round.deferred)
        signature = tuple(sorted(new_metrics.items()))
        if signature in seen:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                "Intrinsic measurements oscillated between sizing passes.",
            )
        seen.add(signature)
        current = next_round
    raise SFLEError(
        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
        "Recursive intrinsic measurement did not converge.",
    )
