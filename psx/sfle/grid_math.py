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
