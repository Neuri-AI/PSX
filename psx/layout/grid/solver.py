"""Engine-neutral Cinnamon Grid entry point.

Native width allocations and final rectangles are calculated by _sfle_native
when the selected Cinnamon engine is Rust. The optional Python solver is
imported ONLY when Python was explicitly selected because native is absent.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from psx.layout.grid.contracts import (
    GridSlot, GridItemConstraints, GridConstrainedRect, GridPackingError,
)


def _validate_grid_input(
    slots, content_width, column_gap, row_gap, item_heights,
    constraints, *, rtl,
) -> None:
    """Shared *input validation*, not solver math, for the two backends.

    Rust never imports the Python numerical fallback. Exact diagnostics for
    malformed declarations are nevertheless part of the shared public API.
    """
    from psx.layout.contracts.fixed_point import I32_MAX

    if not isinstance(slots, (tuple, list)):
        raise GridPackingError("Grid items must be a tuple or list.")
    seen = set()
    for item in slots:
        if not isinstance(item, GridSlot):
            raise GridPackingError("Grid requires GridSlot inputs.")
        if not isinstance(item.id, str) or not item.id or item.id in seen:
            raise GridPackingError("Grid item IDs must be unique nonempty strings.")
        seen.add(item.id)
        if item.span != "auto" and (
            type(item.span) is not int or not 1 <= item.span <= 12
        ):
            raise GridPackingError("Grid span must be 'auto' or an integer 1..12.")
        if type(item.offset) is not int or not 0 <= item.offset <= 11:
            raise GridPackingError("Grid offset must be an integer 0..11.")
        if type(item.order) is not int:
            raise GridPackingError("Grid order must be an integer.")
        if item.span != "auto" and item.span + item.offset > 12:
            raise GridPackingError("Grid span + offset exceeds twelve columns.")

    for name, value in (
        ("content_width", content_width), ("column_gap", column_gap),
        ("row_gap", row_gap),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise GridPackingError(f"{name} must be a finite nonnegative number.")
        if value * 64 > I32_MAX:
            raise GridPackingError(f"{name} exceeds representable LayoutUnit range.")
    if type(rtl) is not bool:
        raise GridPackingError("rtl must be a boolean.")
    if not isinstance(item_heights, dict):
        raise GridPackingError("item_heights must map every item ID to a height.")
    for item in slots:
        if item.id not in item_heights:
            raise GridPackingError(f"Missing height for Grid item {item.id!r}.")
        value = item_heights[item.id]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise GridPackingError("Grid item height must be finite and nonnegative.")
        if value * 64 > I32_MAX:
            raise GridPackingError("Grid item height exceeds representable LayoutUnit range.")

    limits = {} if constraints is None else constraints
    if not isinstance(limits, dict) or not limits.keys() <= seen:
        raise GridPackingError("Grid constraints must reference declared item IDs.")
    # Unspecified constraints are the immutable, already valid defaults. Do
    # not allocate and revalidate one default dataclass per GridItem.
    for bound in limits.values():
        if not isinstance(bound, GridItemConstraints):
            raise GridPackingError("Grid item constraints must be GridItemConstraints.")
        for value in (bound.min_width, bound.max_width,
                      bound.min_height, bound.max_height):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 or value * 64 > I32_MAX
            ):
                raise GridPackingError(
                    "Grid min/max must be finite representable nonnegative lengths."
                )
        if bound.max_width is not None and bound.max_width < bound.min_width:
            raise GridPackingError("Grid max_width cannot be smaller than min_width.")
        if bound.max_height is not None and bound.max_height < bound.min_height:
            raise GridPackingError("Grid max_height cannot be smaller than min_height.")


def compute_grid(
    slots: Sequence[GridSlot],
    content_width: float,
    column_gap: float = 0,
    row_gap: float = 0,
    item_heights: Mapping[str, float] | None = None,
    constraints: Mapping[str, GridItemConstraints] | None = None,
    *,
    rtl: bool = False,
    engine: object | None = None,
) -> tuple[tuple[GridConstrainedRect, ...], ...]:
    if engine is None:
        from psx.layout.engine.backend import load_layout_engine
        engine = load_layout_engine()
    if not getattr(engine, "_validates_grid_input", False):
        _validate_grid_input(
            slots, content_width, column_gap, row_gap,
            item_heights, constraints, rtl=rtl,
        )
    compute = getattr(engine, "compute_grid", None)
    if not callable(compute):
        raise TypeError("Cinnamon Grid requires an engine with compute_grid().")
    return compute(
        slots, content_width, column_gap, row_gap,
        item_heights, constraints, rtl=rtl,
    )


def grid_widths(
    slots: Sequence[GridSlot],
    content_width: float,
    column_gap: float,
    *,
    engine: object | None = None,
) -> dict[str, float]:
    """Use actual Cinnamon allocation with zero heights only for width planning.

    A height of zero is NOT an estimated intrinsic size: rows have no vertical
    measurement at this stage, and this output is used for widths only.
    """
    rows = compute_grid(
        slots, content_width, column_gap,
        item_heights={slot.id: 0.0 for slot in slots},
        engine=engine,
    )
    return {cell.id: cell.width_raw / 64 for row in rows for cell in row}
