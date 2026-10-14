"""Executable Grid line-membership specification shared with Rust."""
from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from psx.sfle.grid_math import (
    GridPackingError, GridSlot, pack_grid_rows,
)

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "grid_row_packing.json")
    .read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["name"])
def test_canonical_grid_row_membership(case):
    items = [GridSlot(**item) for item in case["items"]]
    if case.get("error") == "invalid":
        with pytest.raises(GridPackingError):
            pack_grid_rows(items)
        return
    actual = pack_grid_rows(items)
    assert len(actual) == len(case["rows"])
    for row, expected in zip(actual, case["rows"], strict=True):
        assert len(row.items) == len(expected)
        for item, target in zip(row.items, expected, strict=True):
            assert item.id == target["id"]
            assert item.start == pytest.approx(target["start"], abs=1e-10)
            assert item.span == pytest.approx(target["span"], abs=1e-10)


@pytest.mark.parametrize("invalid", (
    GridSlot("a", span=True),
    GridSlot("a", span=1.5),
    GridSlot("a", span="unknown"),
    GridSlot("a", span=13),
    GridSlot("a", span=0),
    GridSlot("a", offset=True),
    GridSlot("a", offset=-1),
    GridSlot("a", offset=12),
    GridSlot("a", order=True),
    GridSlot("a", order=1.0),
    GridSlot("", span=1),
))
def test_invalid_grid_declarations_fail_closed(invalid):
    with pytest.raises(GridPackingError):
        pack_grid_rows([invalid])


def test_grid_rows_are_deterministic_for_seeded_valid_declarations():
    rng = random.Random(2041)
    for _ in range(200):
        slots = [
            GridSlot(str(n), span=rng.choice(["auto", 1, 2, 3, 4, 6, 8, 12]),
                     order=rng.randint(-2, 2))
            for n in range(rng.randint(0, 24))
        ]
        before = list(slots)
        first = pack_grid_rows(slots)
        second = pack_grid_rows(tuple(slots))
        assert first == second
        assert slots == before
        flattened = [item for row in first for item in row.items]
        assert sorted(item.id for item in flattened) == sorted(item.id for item in slots)
        for row in first:
            assert all(item.span > 0 for item in row.items)
            assert all(item.start >= 0 and item.start + item.span <= 12 + 1e-9
                       for item in row.items)
            assert all(left.start + left.span <= right.start + 1e-9
                       for left, right in zip(row.items, row.items[1:]))


def test_grid_rejects_duplicate_ids_and_nonsequence_inputs():
    with pytest.raises(GridPackingError):
        pack_grid_rows([GridSlot("same"), GridSlot("same")])
    with pytest.raises(GridPackingError):
        pack_grid_rows(None)


PIXEL_CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "grid_pixel_projection.json")
    .read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", PIXEL_CASES, ids=lambda item: item["name"])
def test_fixed_point_pixel_projection_matches_shared_rust_fixtures(case):
    from psx.sfle.grid_math import project_grid_rows
    rows = pack_grid_rows([GridSlot(**item) for item in case["items"]])
    if case.get("error") == "invalid":
        with pytest.raises(GridPackingError):
            project_grid_rows(rows, case["width"], case["gap"])
        return
    actual = project_grid_rows(rows, case["width"], case["gap"])
    assert [
        [{"id": box.id, "x_raw": box.x_raw, "width_raw": box.width_raw}
         for box in row.items] for row in actual
    ] == case["rows"]


@pytest.mark.parametrize("width,gap", (
    (float("nan"), 0), (-1, 0), (True, 0),
    (100, float("inf")), (100, -1), (100, True),
))
def test_pixel_projection_rejects_invalid_constraints(width, gap):
    from psx.sfle.grid_math import project_grid_rows
    rows = pack_grid_rows([GridSlot("a", "auto")])
    with pytest.raises(GridPackingError):
        project_grid_rows(rows, width, gap)


def test_pixel_projection_does_not_accumulate_edge_drift():
    from psx.sfle.grid_math import project_grid_rows
    rows = pack_grid_rows([GridSlot(str(index), "auto") for index in range(11)])
    projection = project_grid_rows(rows, 109.17, 0.31)[0].items
    gap_raw = round(0.31 * 64)
    assert all(left.x_raw + left.width_raw + gap_raw == right.x_raw
               for left, right in zip(projection, projection[1:]))
    assert projection[-1].x_raw + projection[-1].width_raw == round(109.17 * 64)


CROSS_AXIS_CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "grid_cross_axis.json")
    .read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CROSS_AXIS_CASES, ids=lambda item: item["name"])
def test_grid_rtl_and_cross_axis_shared_fixtures(case):
    from psx.sfle.grid_math import layout_grid_rects
    rows = pack_grid_rows([GridSlot(**item) for item in case["items"]])
    if case.get("error") == "invalid":
        with pytest.raises(GridPackingError):
            layout_grid_rects(rows, case["width"], case["gap"],
                              case["row_gap"], case["heights"], rtl=case["rtl"])
        return
    actual = layout_grid_rects(rows, case["width"], case["gap"],
                               case["row_gap"], case["heights"], rtl=case["rtl"])
    assert [
        [{"id": rect.id, "x_raw": rect.x_raw, "y_raw": rect.y_raw,
          "width_raw": rect.width_raw, "height_raw": rect.height_raw}
         for rect in row] for row in actual
    ] == case["rows"]


@pytest.mark.parametrize("row_gap,heights,rtl", (
    (-1, {"a": 10}, False),
    (float("inf"), {"a": 10}, False),
    (True, {"a": 10}, False),
    (0, {"a": -1}, False),
    (0, {"a": float("nan")}, False),
    (0, {"a": True}, False),
    (0, {}, False),
    (0, {"a": 10}, 1),
))
def test_grid_cross_axis_rejects_invalid_input(row_gap, heights, rtl):
    from psx.sfle.grid_math import layout_grid_rects
    rows = pack_grid_rows([GridSlot("a", 12)])
    with pytest.raises(GridPackingError):
        layout_grid_rects(rows, 120, 0, row_gap, heights, rtl=rtl)


@pytest.mark.parametrize("width,gap", (
    (40_000_000, 0),
    (100, 40_000_000),
))
def test_grid_pixel_projection_rejects_unrepresentable_dimensions(width, gap):
    from psx.sfle.grid_math import project_grid_rows
    rows = pack_grid_rows([GridSlot("a", 6), GridSlot("b", 6)])
    with pytest.raises(GridPackingError, match="LayoutUnit"):
        project_grid_rows(rows, width, gap)


@pytest.mark.parametrize("width,gap,row_gap,heights", (
    (40_000_000, 0, 0, {"a": 10}),
    (100, 0, 40_000_000, {"a": 10}),
    (100, 0, 0, {"a": 40_000_000}),
))
def test_grid_cross_axis_rejects_unrepresentable_dimensions(
    width, gap, row_gap, heights
):
    from psx.sfle.grid_math import layout_grid_rects
    rows = pack_grid_rows([GridSlot("a", 12)])
    with pytest.raises(GridPackingError, match="LayoutUnit"):
        layout_grid_rects(rows, width, gap, row_gap, heights)


def test_grid_cross_axis_rejects_accumulated_vertical_overflow():
    from psx.sfle.grid_math import layout_grid_rects
    rows = pack_grid_rows([GridSlot("a", 12), GridSlot("b", 12)])
    with pytest.raises(GridPackingError, match="vertical geometry"):
        layout_grid_rects(rows, 100, 0, 10, {"a": 20_000_000, "b": 20_000_000})


def test_grid_fixed_point_maximum_is_not_silently_clamped():
    from psx.sfle.grid_math import project_grid_rows, layout_grid_rects
    limit = 2_147_483_647 / 64
    rows = pack_grid_rows([GridSlot("a", 12)])
    assert project_grid_rows(rows, limit)[0].items[0].width_raw == 2_147_483_647
    assert layout_grid_rects(
        rows, 100, 0, 0, {"a": limit}
    )[0][0].height_raw == 2_147_483_647
    with pytest.raises(GridPackingError):
        project_grid_rows(rows, limit + 1 / 64)
    with pytest.raises(GridPackingError):
        layout_grid_rects(rows, 100, 0, 0, {"a": limit + 1 / 64})
