"""F2.2.4 explicit CSS child-size resolution at the measurement boundary.

The *parent content box* must be supplied by an upstream layout/measurement
stage. Parent available constraints are not assumed equal to content-box
dimensions, and unresolved CSS keywords are preserved as indefinite axes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .lengths import Length
from .measurement_plan import MeasurementPlan, plan_measurements
from .model import AvailableSize, LayoutConstraints, LayoutInput
from .sizing import ResolutionKind, SizeProperty, resolve_length


@dataclass(frozen=True, slots=True)
class ChildSizing:
    """Specified width/height; never confused with a used size or flex basis."""

    width: Length
    height: Length

    def __post_init__(self) -> None:
        if not isinstance(self.width, Length) or not isinstance(self.height, Length):
            raise TypeError("Child sizing requires typed CSS Length values.")


@dataclass(frozen=True, slots=True)
class ChildConstraintResolution:
    constraints: LayoutConstraints
    width_kind: ResolutionKind
    height_kind: ResolutionKind


def resolve_child_constraints(
    containing_content: LayoutConstraints,
    sizing: ChildSizing,
) -> ChildConstraintResolution:
    """Derive definite child dimensions only for resolved CSS px/percent.

    Width percentages reference containing content inline width; height
    percentages reference its block height in horizontal writing mode.
    auto/intrinsic/indefinite percent dimensions remain *indefinite*.
    This is intentionally not an automatic flex-item stretch or flex sizing.
    """
    if not isinstance(containing_content, LayoutConstraints):
        raise TypeError("containing_content must be LayoutConstraints.")
    if not isinstance(sizing, ChildSizing):
        raise TypeError("sizing must be ChildSizing.")
    def resolve(length: Length, prop: SizeProperty, axis: AvailableSize):
        result = resolve_length(
            length, prop,
            containing_inline_size=containing_content.width,
            containing_block_axis_size=axis,
            flex_container_main_size=containing_content.width,
        )
        return (
            AvailableSize(result.value, True)
            if result.kind == ResolutionKind.USED
            else AvailableSize(None, False),
            result.kind,
        )
    width, width_kind = resolve(sizing.width, SizeProperty.WIDTH, containing_content.width)
    height, height_kind = resolve(sizing.height, SizeProperty.HEIGHT, containing_content.height)
    return ChildConstraintResolution(
        LayoutConstraints(width, height), width_kind, height_kind,
    )


def plan_styled_measurements(
    snapshot: LayoutInput,
    *,
    parent_content: tuple[tuple[str, LayoutConstraints], ...],
    child_sizing: tuple[tuple[str, ChildSizing], ...],
    revisions: tuple[tuple[str, int], ...] = (),
) -> MeasurementPlan:
    """Bridge explicit parent content snapshots into the existing worklist.

    Every non-root node must have its parent's *measured used content-box*
    dimensions and a typed child sizing declaration. Never substitute an
    ancestor's available size or a possibly stale intrinsic width.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("snapshot must be LayoutInput.")
    if not isinstance(parent_content, tuple) or not isinstance(child_sizing, tuple):
        raise TypeError("Parent content and child styles must be tuples.")
    node_ids = {node.node_id for node in snapshot.nodes}
    def checked_map(entries, kind):
        data = {}
        for node_id, value in entries:
            if not isinstance(node_id, str) or node_id not in node_ids or node_id in data:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Unknown/duplicate node style or content.")
            if not isinstance(value, kind):
                raise TypeError(f"Expected {kind.__name__} for node {node_id}.")
            data[node_id] = value
        return data
    content = checked_map(parent_content, LayoutConstraints)
    styles = checked_map(child_sizing, ChildSizing)
    if not snapshot.nodes:
        if content or styles:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Metadata without tree.")
        return plan_measurements(snapshot, revisions=revisions)
    root = snapshot.nodes[0].node_id
    if root in styles:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Root style does not define a child constraint.")
    children = []
    for node in snapshot.nodes[1:]:
        if node.node_id not in styles or node.parent_id not in content:
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Missing sizing or established parent content box for {node.node_id}.",
            )
        resolved = resolve_child_constraints(content[node.parent_id], styles[node.node_id])
        children.append((node.node_id, resolved.constraints))
    return plan_measurements(snapshot, child_constraints=tuple(children), revisions=revisions)


def plan_used_box_measurements(
    snapshot: LayoutInput,
    *,
    used_boxes: tuple[tuple[str, "BoxRect"], ...],
    child_sizing: tuple[tuple[str, ChildSizing], ...],
    revisions: tuple[tuple[str, int], ...] = (),
) -> MeasurementPlan:
    """Feed established CSS used content-box dimensions to the measurement plan.

    The caller must establish *current-generation* used box geometry before
    calling this function. Neither an available-size hint nor a border-box
    dimension is interchangeable with its content-box dimension. This adapter
    does not solve the parent/child sizing dependency cycle.
    """
    from .model import BoxRect

    if not isinstance(snapshot, LayoutInput):
        raise TypeError("snapshot must be LayoutInput.")
    if not isinstance(used_boxes, tuple):
        raise TypeError("used_boxes must be a tuple.")
    node_ids = {node.node_id for node in snapshot.nodes}
    seen: set[str] = set()
    content: list[tuple[str, LayoutConstraints]] = []
    for node_id, box in used_boxes:
        if not isinstance(node_id, str) or node_id not in node_ids or node_id in seen:
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT, "Unknown/duplicate used box."
            )
        if not isinstance(box, BoxRect):
            raise TypeError("Used boxes must be BoxRect values.")
        seen.add(node_id)
        content.append((
            node_id,
            LayoutConstraints(
                AvailableSize(box.content.width, True),
                AvailableSize(box.content.height, True),
            ),
        ))
    return plan_styled_measurements(
        snapshot,
        parent_content=tuple(content),
        child_sizing=child_sizing,
        revisions=revisions,
    )
