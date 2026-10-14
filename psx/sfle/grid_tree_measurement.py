"""Bridge normalized Grid identity and native intrinsic receipts into Cinnamon.

The caller supplies already measured MeasuredBox records from the existing
native measurement ports. This module never measures, creates, or mounts
widgets, and never invents intrinsic dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from psx.core.grid_contract import (
    normalize_grid_props, normalize_grid_item_props, resolve_grid_item_props,
)
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind

from .fixed_point import LayoutUnit
from .grid_math import GridConstrainedRect, GridItemConstraints, GridPackingError, GridSlot, compute_grid
from .grid_native_plan import GridNativePlacement, plan_grid_native_geometry
from .lengths import parse_length, LengthKind
from .model import MeasuredBox
from .native_layout_snapshot import path_identity


@dataclass(frozen=True, slots=True)
class PreparedGridMeasurement:
    """Pure, immutable native measurement handoff; not a mounted Grid."""
    grid_id: str
    generation: int
    child_ids: tuple[str, ...]
    measurement_revisions: tuple[tuple[str, int], ...]
    rows: tuple[tuple[GridConstrainedRect, ...], ...]
    placements: tuple[GridNativePlacement, ...]


def _pixel(value: object, name: str) -> float:
    try:
        parsed = parse_length(value)
    except (TypeError, ValueError) as exc:
        raise GridPackingError(f"{name} requires a finite pixel length.") from exc
    if parsed.kind is not LengthKind.PX or parsed.value is None or parsed.value < 0:
        raise GridPackingError(f"{name} requires a finite nonnegative pixel length.")
    return LayoutUnit.from_nearest(parsed.value).to_px()


def prepare_grid_measurement(
    grid: NormalizedLayoutNode,
    *,
    content_width: float,
    measurements: Sequence[MeasuredBox],
    mounted_ids: Sequence[str],
    generation: int,
    current_generation: int,
    constraints: Mapping[str, GridItemConstraints] | None = None,
    rtl: bool = False,
) -> PreparedGridMeasurement:
    """Resolve responsive Grid items against the Grid content box.

    Requires one native measurement per direct GridItem identity. The native
    measurement layer owns the supplied preferred heights and revisions;
    nested child measurement is outside this handoff's scope.
    """
    if not isinstance(grid, NormalizedLayoutNode) or grid.kind is not NodeKind.HOST or grid.type != "Grid":
        raise GridPackingError("Expected a normalized Grid host.")
    if type(rtl) is not bool:
        raise GridPackingError("Grid writing direction must be bool.")
    if isinstance(content_width, bool) or not isinstance(content_width, (int, float)):
        raise GridPackingError("Grid content width must be a definite numeric value.")
    from math import isfinite
    from .fixed_point import I32_MAX
    if not isfinite(content_width) or content_width < 0 or content_width * 64 > I32_MAX:
        raise GridPackingError("Grid content width is invalid or unrepresentable.")
    props = normalize_grid_props(grid.source.props)
    children = grid.effective_children
    slots: list[GridSlot] = []
    ids: list[str] = []
    for child in children:
        if child.kind is not NodeKind.HOST or child.type != "GridItem":
            raise GridPackingError("Grid requires direct GridItem participants.")
        if len(child.effective_children) != 1:
            raise GridPackingError("GridItem requires exactly one effective child.")
        identifier = path_identity(child.path)
        values = resolve_grid_item_props(
            normalize_grid_item_props(child.source.props), content_width,
        )
        slots.append(GridSlot(identifier, values["span"], values["offset"]))
        ids.append(identifier)
    if len(set(ids)) != len(ids):
        raise GridPackingError("Duplicate normalized Grid child identities.")
    if not isinstance(measurements, (tuple, list)) or any(
        not isinstance(measurement, MeasuredBox) for measurement in measurements
    ):
        raise GridPackingError("Grid requires actual MeasuredBox receipts.")
    measured = {measurement.node_id: measurement for measurement in measurements}
    if len(measured) != len(measurements) or set(measured) != set(ids):
        raise GridPackingError("Grid measurements must match direct GridItem identities exactly.")
    for measurement in measurements:
        if not measurement.constraints.width.definite:
            raise GridPackingError("Grid measurement requires a definite width constraint.")
        if measurement.constraints.width.value is None:
            raise GridPackingError("Grid measurement width is missing.")
    limits = {} if constraints is None else dict(constraints)
    heights = {
        item_id: measured[item_id].intrinsic.preferred_height for item_id in ids
    }
    rows = compute_grid(
        slots, content_width, _pixel(props["column_gap"], "Grid.column_gap"),
        _pixel(props["row_gap"], "Grid.row_gap"),
        heights, limits, rtl=rtl,
    )
    placements = plan_grid_native_geometry(
        rows, expected_ids=ids, measured_ids=tuple(measured),
        mounted_ids=mounted_ids, generation=generation,
        current_generation=current_generation,
    )
    return PreparedGridMeasurement(
        path_identity(grid.path), generation, tuple(ids),
        tuple((identifier, measured[identifier].revision) for identifier in ids),
        rows, placements,
    )
