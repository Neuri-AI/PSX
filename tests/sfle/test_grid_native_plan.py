"""Native Grid placement preflight: executable behavior, not mock widget receipts."""
from __future__ import annotations

from dataclasses import replace
import pytest

from psx.sfle.grid_math import (
    GridSlot, GridItemConstraints, GridPackingError, compute_grid,
)
from psx.sfle.grid_native_plan import plan_grid_native_geometry


def batch(rows, *, ids=("a", "b"), measured=None, mounted=None, generation=4, current=4):
    return plan_grid_native_geometry(
        rows, expected_ids=ids,
        measured_ids=ids if measured is None else measured,
        mounted_ids=ids if mounted is None else mounted,
        generation=generation, current_generation=current,
    )


def constrained_rows():
    return compute_grid(
        [GridSlot("a", 6), GridSlot("b", 6)], 120,
        item_heights={"a": 10, "b": 10},
        constraints={"a": GridItemConstraints(min_width=70)},
    )


def test_placement_batch_preserves_allocations_and_overflow_receipts():
    placements = batch(constrained_rows())
    assert tuple(item.node_id for item in placements) == ("a", "b")
    assert (placements[0].x, placements[0].width) == (0, 60)
    assert (placements[1].x, placements[1].width) == (60, 60)
    assert placements[0].used_width == 70
    assert placements[0].width == 60
    assert placements[0].used_height == 10
    assert placements[1].used_width == 60
    assert placements[0].overflow_x and not placements[1].overflow_x


@pytest.mark.parametrize("kwargs", (
    {"measured": ("a",)},
    {"mounted": ("a", "missing")},
    {"ids": ("a", "a")},
    {"ids": ("a", "b", "c")},
    {"generation": 3},
    {"generation": True},
))
def test_preflight_rejects_incomplete_or_stale_batches(kwargs):
    with pytest.raises(GridPackingError):
        batch(constrained_rows(), **kwargs)


def test_preflight_rejects_duplicate_solver_receipts():
    rows = constrained_rows()
    with pytest.raises(GridPackingError):
        batch((rows[0], rows[0]))


def test_preflight_rejects_corrupted_overflow_receipts():
    rows = constrained_rows()
    corrupt = replace(rows[0][0], overflow_x=False)
    with pytest.raises(GridPackingError):
        batch(((corrupt, rows[0][1]),))


def test_preflight_rejects_unrepresentable_coordinates():
    rows = constrained_rows()
    corrupt = replace(rows[0][0], x_raw=2_147_483_648)
    with pytest.raises(GridPackingError):
        batch(((corrupt, rows[0][1]),))


def test_empty_grid_is_a_valid_empty_batch():
    assert plan_grid_native_geometry(
        (), expected_ids=(), measured_ids=(), mounted_ids=(),
        generation=0, current_generation=0,
    ) == ()


def test_rtl_coordinates_remain_solver_owned():
    rows = compute_grid(
        [GridSlot("a", 3), GridSlot("b", 3)], 120,
        item_heights={"a": 10, "b": 10}, rtl=True,
    )
    placements = batch(rows)
    assert placements[0].x == 90
    assert placements[1].x == 60


def test_native_plan_keeps_max_constrained_used_size_separate_from_allocation():
    rows = compute_grid(
        [GridSlot("a", 6), GridSlot("b", 6)], 120,
        item_heights={"a": 20, "b": 20},
        constraints={"a": GridItemConstraints(max_width=35, max_height=8)},
    )
    placements = batch(rows)
    assert (placements[0].width, placements[0].used_width) == (60, 35)
    assert (placements[0].height, placements[0].used_height) == (20, 8)
    assert placements[1].x == 60
    assert not placements[0].overflow_x
    assert not placements[0].overflow_y


def test_native_plan_preserves_fractional_layout_unit_precision():
    rows = compute_grid(
        [GridSlot("a", 6), GridSlot("b", 6)], 101,
        item_heights={"a": 1.5, "b": 1.5},
    )
    placements = batch(rows)
    assert placements[0].width * 64 == rows[0][0].width_raw
    assert placements[1].x * 64 == rows[0][1].x_raw
    assert placements[0].used_height == 1.5


@pytest.mark.parametrize("change", (
    {"x_raw": 2_147_483_640, "width_raw": 20},
    {"y_raw": 2_147_483_640, "height_raw": 20},
    {"id": ""},
))
def test_native_plan_rejects_forged_edges_and_invalid_identity(change):
    rows = constrained_rows()
    corrupt = replace(rows[0][0], **change)
    with pytest.raises(GridPackingError):
        batch(((corrupt, rows[0][1]),))
