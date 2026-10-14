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
