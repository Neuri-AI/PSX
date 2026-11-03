"""Immutable Grid data contracts shared by both Cinnamon backends.

No row packing, pixel allocation, or layout math is implemented here.
"""
from __future__ import annotations
from dataclasses import dataclass

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




@dataclass(frozen=True, slots=True)
class GridPixelItem:
    """Projected horizontal box; coordinates are exact signed 1/64px units."""
    id: str
    x_raw: int
    width_raw: int


@dataclass(frozen=True, slots=True)
class GridPixelRow:
    items: tuple[GridPixelItem, ...]




@dataclass(frozen=True, slots=True)
class GridRect:
    """Projected Grid item geometry in 1/64px units."""
    id: str
    x_raw: int
    y_raw: int
    width_raw: int
    height_raw: int




@dataclass(frozen=True, slots=True)
class GridItemConstraints:
    """Resolved nonnegative content-box min/max limits; None means unbounded."""
    min_width: float = 0
    max_width: float | None = None
    min_height: float = 0
    max_height: float | None = None


@dataclass(frozen=True, slots=True)
class GridConstrainedRect:
    """Immutable allocated rectangle and independently constrained used size."""
    id: str
    x_raw: int
    y_raw: int
    width_raw: int
    height_raw: int
    used_width_raw: int
    used_height_raw: int
    overflow_x: bool
    overflow_y: bool


