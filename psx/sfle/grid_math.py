"""Renderer-neutral 12-column Grid row packing; no native geometry or pixels.

The explicit spans and offsets reserve logical column units. Automatic items
take equal shares of the remainder of their *finalized* row. Later items never
retroactively change closed row membership. This module is the Python parity
implementation; Rust mirrors its validated rules.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class GridSlot:
    id: str
    span: int | str = "auto"
    offset: int = 0
    order: int = 0


@dataclass(frozen=True, slots=True)
class PackedGridItem:
    id: str
    start: float
    span: float


@dataclass(frozen=True, slots=True)
class PackedGridRow:
    items: tuple[PackedGridItem, ...]


class GridPackingError(ValueError):
    """Grid declaration cannot be placed within twelve logical columns."""


def _validate(items: tuple[GridSlot, ...]) -> None:
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, GridSlot):
            raise GridPackingError("Grid requires GridSlot inputs.")
        if not item.id or item.id in ids or not isinstance(item.id, str):
            raise GridPackingError("Grid item IDs must be unique nonempty strings.")
        ids.add(item.id)
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


def _finalize(items: list[GridSlot]) -> PackedGridRow:
    used = sum(item.offset + (item.span if isinstance(item.span, int) else 0)
               for item in items)
    autos = sum(item.span == "auto" for item in items)
    remaining = 12 - used
    if used > 12 or (autos and remaining <= 0):
        raise GridPackingError("Grid row has no remaining space for auto items.")
    share = remaining / autos if autos else 0.0
    cursor = 0.0
    placements: list[PackedGridItem] = []
    for item in items:
        cursor += item.offset
        span = share if item.span == "auto" else float(item.span)
        placements.append(PackedGridItem(item.id, cursor, span))
        cursor += span
    return PackedGridRow(tuple(placements))


def pack_grid_rows(items: tuple[GridSlot, ...] | list[GridSlot]) -> tuple[PackedGridRow, ...]:
    """Deterministic, stable order-aware Grid line membership and logical units.

    An explicit item can stay on a row with pending auto items only when
    positive capacity remains for those autos. A closed row cannot be changed
    by a subsequent item. The function does not compute pixel geometry.
    """
    if not isinstance(items, (tuple, list)):
        raise GridPackingError("Grid items must be a tuple or list.")
    slots = tuple(items)
    _validate(slots)
    ordered = sorted(slots, key=lambda item: item.order)
    rows: list[PackedGridRow] = []
    current: list[GridSlot] = []
    explicit_used = 0
    autos = 0
    for item in ordered:
        reservation = item.offset + (item.span if isinstance(item.span, int) else 0)
        # Auto needs a positive share; it cannot join a fully reserved row.
        would_exhaust_autos = (autos > 0 or item.span == "auto") and (
            explicit_used + reservation >= 12
        )
        if current and (explicit_used + reservation > 12 or would_exhaust_autos):
            rows.append(_finalize(current))
            current = []
            explicit_used = 0
            autos = 0
        current.append(item)
        explicit_used += reservation
        autos += item.span == "auto"
    if current:
        rows.append(_finalize(current))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class GridPixelItem:
    """Projected horizontal box; coordinates are exact signed 1/64px units."""
    id: str
    x_raw: int
    width_raw: int


@dataclass(frozen=True, slots=True)
class GridPixelRow:
    items: tuple[GridPixelItem, ...]


def _nearest_positive_fraction(numerator: int, denominator: int) -> int:
    return (numerator * 2 + denominator) // (2 * denominator)


def project_grid_rows(
    rows: tuple[PackedGridRow, ...] | list[PackedGridRow],
    content_width: int | float,
    column_gap: int | float = 0,
) -> tuple[GridPixelRow, ...]:
    """Project logical Grid rows onto deterministic 1/64px edges.

    Gaps occur only between *rendered siblings*, never at empty offsets.
    The logical twelve-column capacity is scaled from the remaining width
    after the actual between-widget gaps. Adjacent edges use a single shared
    rounding origin, preventing per-item cumulative drift.
    """
    from .fixed_point import LayoutUnit

    for name, value in (("content_width", content_width),
                        ("column_gap", column_gap)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (
            not math.isfinite(value) or value < 0
        ):
            raise GridPackingError(f"{name} must be a finite nonnegative number.")
    if not isinstance(rows, (tuple, list)) or any(
        not isinstance(row, PackedGridRow) for row in rows
    ):
        raise GridPackingError("Grid pixel projection requires packed rows.")
    width = LayoutUnit.from_nearest(content_width).raw
    gap = LayoutUnit.from_nearest(column_gap).raw
    if content_width * 64 > 2_147_483_647 or column_gap * 64 > 2_147_483_647:
        raise GridPackingError("Grid width or gap exceeds representable LayoutUnit range.")
    result: list[GridPixelRow] = []
    for row in rows:
        count = len(row.items)
        if count == 0:
            result.append(GridPixelRow(()))
            continue
        required_gaps = (count - 1) * gap
        if required_gaps > width:
            raise GridPackingError("Grid column gaps exceed content width.")
        usable = width - required_gaps
        boxes: list[GridPixelItem] = []
        previous_end = 0
        for index, item in enumerate(row.items):
            if not all(math.isfinite(value) for value in (item.start, item.span)):
                raise GridPackingError("Grid logical geometry must be finite.")
            if item.start < 0 or item.span <= 0 or item.start + item.span > 12 + 1e-9:
                raise GridPackingError("Grid logical geometry exceeds twelve columns.")
            start_units = _nearest_positive_fraction(math.floor(item.start * 1_000_000_000 + 0.5) * usable, 12_000_000_000)
            end_units = _nearest_positive_fraction(math.floor((item.start + item.span) * 1_000_000_000 + 0.5) * usable, 12_000_000_000)
            x = start_units + index * gap
            end = end_units + index * gap
            if x < previous_end or end < x or end > 2_147_483_647:
                raise GridPackingError("Grid projected edges overlap or invert.")
            boxes.append(GridPixelItem(item.id, x, end - x))
            previous_end = end
        result.append(GridPixelRow(tuple(boxes)))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class GridRect:
    """Projected Grid item geometry in 1/64px units."""
    id: str
    x_raw: int
    y_raw: int
    width_raw: int
    height_raw: int


def layout_grid_rects(
    rows: tuple[PackedGridRow, ...] | list[PackedGridRow],
    content_width: int | float,
    column_gap: int | float = 0,
    row_gap: int | float = 0,
    item_heights: dict[str, int | float] | None = None,
    *,
    rtl: bool = False,
) -> tuple[tuple[GridRect, ...], ...]:
    """Project horizontal direction and row cross-axis without native mounting.

    Row height is the maximum declared item height. Heights are required for
    every item; intrinsic measurement belongs to later integration stages.
    """
    from .fixed_point import LayoutUnit

    if type(rtl) is not bool:
        raise GridPackingError("rtl must be a boolean.")
    if not isinstance(row_gap, (int, float)) or isinstance(row_gap, bool) or (
        not math.isfinite(row_gap) or row_gap < 0
    ):
        raise GridPackingError("row_gap must be finite and nonnegative.")
    if not isinstance(item_heights, dict):
        raise GridPackingError("item_heights must map every item ID to a height.")
    projected = project_grid_rows(rows, content_width, column_gap)
    width = LayoutUnit.from_nearest(content_width).raw
    gap = LayoutUnit.from_nearest(row_gap).raw
    if row_gap * 64 > 2_147_483_647:
        raise GridPackingError("Grid row gap exceeds representable LayoutUnit range.")
    heights: dict[str, int] = {}
    for row in projected:
        for item in row.items:
            if item.id not in item_heights:
                raise GridPackingError(f"Missing height for Grid item {item.id!r}.")
            value = item_heights[item.id]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (
                not math.isfinite(value) or value < 0
            ):
                raise GridPackingError("Grid item height must be finite and nonnegative.")
            if value * 64 > 2_147_483_647:
                raise GridPackingError("Grid item height exceeds representable LayoutUnit range.")
            heights[item.id] = LayoutUnit.from_nearest(value).raw
    y = 0
    result: list[tuple[GridRect, ...]] = []
    for row in projected:
        if y > 2_147_483_647 or (row.items and y + max(heights[item.id] for item in row.items) > 2_147_483_647):
            raise GridPackingError("Grid vertical geometry exceeds LayoutUnit range.")
        result.append(tuple(
            GridRect(
                item.id,
                width - item.x_raw - item.width_raw if rtl else item.x_raw,
                y,
                item.width_raw,
                heights[item.id],
            ) for item in row.items
        ))
        if row.items:
            y += max(heights[item.id] for item in row.items) + gap
    return tuple(result)
