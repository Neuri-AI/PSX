"""Renderer-neutral Grid native-commit preflight.

This module never creates or moves toolkit widgets. It converts Cinnamon's
fixed-point Grid output into a complete, identity-checked placement batch.
The renderer must commit the batch on its owning UI thread and perform native
readback; an incomplete batch is rejected before the first native mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from .fixed_point import I32_MAX
from .grid_math import GridConstrainedRect, GridPackingError


@dataclass(frozen=True, slots=True)
class GridNativePlacement:
    node_id: str
    x: float
    y: float
    width: float
    height: float
    overflow_x: bool
    overflow_y: bool


def plan_grid_native_geometry(
    rows: Sequence[Sequence[GridConstrainedRect]],
    *,
    expected_ids: Sequence[str],
    measured_ids: Sequence[str],
    mounted_ids: Sequence[str],
    generation: int,
    current_generation: int,
) -> tuple[GridNativePlacement, ...]:
    """Preflight an entire Grid child batch before native commit.

    The expected IDs are stable reconciler identities, not widget names.
    Allocated rectangles (not potentially overflowing used sizes) determine
    sibling placement. Measured and mounted membership must match exactly.
    """
    if type(generation) is not int or type(current_generation) is not int:
        raise GridPackingError("Grid generation must be an integer.")
    if generation != current_generation:
        raise GridPackingError("Stale Grid geometry generation.")
    expected = tuple(expected_ids)
    if any(type(value) is not str or not value for value in expected):
        raise GridPackingError("Grid requires nonempty unique child identities.")
    if len(set(expected)) != len(expected):
        raise GridPackingError("Duplicate Grid child identities.")
    for name, ids in (("measured", measured_ids), ("mounted", mounted_ids)):
        ids = tuple(ids)
        if len(ids) != len(expected) or set(ids) != set(expected):
            raise GridPackingError(f"Grid {name} child identity mismatch.")
    placements: list[GridNativePlacement] = []
    for row in rows:
        for rect in row:
            if not isinstance(rect, GridConstrainedRect):
                raise GridPackingError("Grid commit requires constrained Cinnamon rectangles.")
            for value in (rect.x_raw, rect.y_raw, rect.width_raw, rect.height_raw,
                          rect.used_width_raw, rect.used_height_raw):
                if type(value) is not int or not 0 <= value <= I32_MAX:
                    raise GridPackingError("Grid geometry must be representable LayoutUnit units.")
            if rect.overflow_x != (rect.used_width_raw > rect.width_raw) or (
                rect.overflow_y != (rect.used_height_raw > rect.height_raw)
            ):
                raise GridPackingError("Grid overflow receipts disagree with used geometry.")
            placements.append(GridNativePlacement(
                rect.id, rect.x_raw / 64, rect.y_raw / 64,
                rect.width_raw / 64, rect.height_raw / 64,
                rect.overflow_x, rect.overflow_y,
            ))
    if len(placements) != len(expected) or set(p.node_id for p in placements) != set(expected):
        raise GridPackingError("Grid solver and mounted identities differ.")
    if len({p.node_id for p in placements}) != len(expected):
        raise GridPackingError("Grid solver returned duplicate child identities.")
    return tuple(placements)
