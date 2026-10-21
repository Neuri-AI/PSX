"""G2: solve actual post-flex widths before trusting native intrinsic heights.

The F2 engine is always the sizing authority: provisional compute obtains the
actual content boxes. Native UI-thread ports measure at those content widths,
then a new immutable snapshot is solved. Iteration is bounded and fails
closed instead of committing guessed/stale geometry.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

from .errors import DiagnosticCode, SFLEError
from .model import AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutResult, MeasuredBox

_MAX_PASSES = 5
_TOLERANCE = 0.01


def compute_width_dependent(
    engine: object,
    snapshot: LayoutInput,
    measure_width: Mapping[str, Callable[[float], IntrinsicSizes]],
    *,
    current_generation: Callable[[], int],
    previous_input: LayoutInput | None = None,
    previous_result: LayoutResult | None = None,
    native_measurement_invalidated: bool = False,
) -> LayoutResult:
    """Finish all height-for-width measurements without native placement.

    The caller must run this on the owning UI thread. Providers must return
    content metrics for the width supplied, not a widget's *allocated* size.
    Width-dependent leaf heights are remeasured after each provisional SFLE
    computation. All final measurements are keyed to the same generation and
    the actual assigned content width (not inherited root viewport width).
    """
    if not measure_width:
        incremental = getattr(engine, "compute_incremental", None)
        if (not native_measurement_invalidated and previous_input is not None
                and previous_result is not None and callable(incremental)):
            return incremental(
                snapshot, previous_input=previous_input,
                previous_result=previous_result,
            )
        return engine.compute(snapshot)
    if not callable(getattr(engine, "compute_provisional", None)):
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "SFLE engine requires compute_provisional for width-dependent leaves.",
        )
    if current_generation() != snapshot.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale SFLE width-measurement generation.")
    by_id = {m.node_id: m for m in snapshot.measurements}
    valid_nodes = {node.node_id for node in snapshot.nodes}
    if not set(measure_width) <= set(by_id) or not set(measure_width) <= valid_nodes:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Width port has no measured SFLE leaf.")
    parents = {node.parent_id for node in snapshot.nodes if node.parent_id is not None}
    if any(node_id in parents for node_id in measure_width):
        raise SFLEError(DiagnosticCode.INVALID_TREE, "Width measurement ports must be leaves.")

    current = snapshot
    # Always execute the provisional stage before any native width measurement;
    # root/parent dimensions are not a valid substitute for child content width.
    for _ in range(_MAX_PASSES):
        if current_generation() != snapshot.generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale SFLE width-measurement generation.")
        result = engine.compute_provisional(current)
        if result.generation != snapshot.generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Provisional SFLE generation mismatch.")
        rects = dict(result.boxes)
        next_measurements = {m.node_id: m for m in current.measurements}
        changed = False
        for node_id, callback in measure_width.items():
            item = rects.get(node_id)
            if item is None:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Provisional SFLE leaf box missing.", node_id)
            width = item.content.width
            previous = next_measurements[node_id]
            axis = previous.constraints.width
            if axis.definite and axis.value is not None and abs(axis.value - width) <= _TOLERANCE:
                # On the very first iteration the source may have measured
                # against a viewport-width placeholder, not this leaf width.
                # The caller is responsible for marking such a source as
                # unconstrained in its first intrinsic measurement.
                continue
            metrics = callback(width)
            if current_generation() != snapshot.generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale native width measurement.", node_id)
            if not isinstance(metrics, IntrinsicSizes):
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Width-dependent port must return IntrinsicSizes.", node_id)
            # Min/max-content inline contributions must remain those of the
            # *unconstrained* native metrics. Only cross/block intrinsic
            # heights and the width-specific revision change here.
            intrinsic = replace(
                previous.intrinsic,
                min_content_height=metrics.min_content_height,
                max_content_height=metrics.max_content_height,
                preferred_height=metrics.preferred_height,
                baseline=metrics.baseline if metrics.baseline is not None else previous.intrinsic.baseline,
            )
            constraints = LayoutConstraints(
                AvailableSize(width, True),
                AvailableSize(None, False),
            )
            next_measurements[node_id] = MeasuredBox(
                node_id, intrinsic, constraints, snapshot.generation,
            )
            changed = True
        if not changed:
            final = engine.compute(current)
            if final.generation != snapshot.generation or current_generation() != snapshot.generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale SFLE final width-dependent result.")
            boxes = dict(final.boxes)
            for node_id in measure_width:
                measured = next_measurements[node_id].constraints.width
                if (node_id not in boxes or measured.value is None or
                        abs(boxes[node_id].content.width - measured.value) > _TOLERANCE):
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Final SFLE width differs from the certified native width measurement.",
                        node_id,
                    )
            return final
        current = replace(current, measurements=tuple(
            next_measurements[item.node_id] for item in current.measurements
        ))
    raise SFLEError(
        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
        "Width-dependent intrinsic sizes failed to converge within five SFLE passes.",
    )


def seed_unconstrained_width_measurements(
    snapshot: LayoutInput, ids: frozenset[str],
) -> LayoutInput:
    """Prevent placeholder root-width hints being mistaken for leaf measures."""
    return replace(snapshot, measurements=tuple(
        replace(
            measured,
            constraints=LayoutConstraints(
                AvailableSize(None, False), AvailableSize(None, False),
            ),
        ) if measured.node_id in ids else measured
        for measured in snapshot.measurements
    ))


def auto_height_measurement_ids(snapshot: LayoutInput) -> frozenset[str]:
    """Select real leaf auto-height participants; explicit height stays CSS fixed."""
    parents = {node.parent_id for node in snapshot.nodes if node.parent_id is not None}
    return frozenset(
        node.node_id for node in snapshot.nodes
        if node.node_id not in parents
        and "layout_height" not in dict(node.style)
        and "height" not in dict(node.style)
    )
