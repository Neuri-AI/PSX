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
    prepared = prepare_measured_leaf_nodes(
        nodes, measurements=first.measurements, leaves=intrinsic_leaves,
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
    provisional = RecursiveMeasurementResult(sized, first.measurements, ())
    # Re-measure against the *allocated* boxes after flex distribution.
    # An existing revision/constraint match is reused by the worklist.
    second = measure_resolved_margin_tree(
        replace(snapshot, measurements=first.measurements),
        prepared,
        child_sizing=_used_sizing(provisional, nodes),
        revisions=revisions,
        port=native_port, current_generation=current_generation,
    )
    # The initial pass might include deferred axes, but the second pass has
    # definite final Flex allocations. The native port can still explicitly
    # reject unsupported width-sensitive measurement.
    return RecursiveMeasurementResult(sized, second.measurements, second.deferred)
