"""Native Rust Grid vs Python Grid: identical 1/64 px allocations.

The Rust branch invokes the PyO3 grid ABI directly through the selected
engine. The Python branch is explicitly selected and imported only here,
inside the differential test (not in native UI runtime).
"""
from __future__ import annotations

import random

import pytest

from psx.layout.engine.backend import RustLayoutEngine
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.contracts import GridSlot, GridItemConstraints
from psx.layout.grid.solver import compute_grid, grid_widths


@pytest.mark.parametrize("rtl", [False, True])
@pytest.mark.parametrize("width,gap,row_gap,spans", [
    (800, 4, 0, [6, 6]),
    (767, 4, 9, [6, 6]),
    (240.37, 2.25, 5.125, ["auto", "auto", "auto"]),
    (1600, 16, 6, [3, 3, 3, 3]),
    (33.125, 2.0, 1.0, [6, 6]),
    (1200, 8, 12, [12, 6, 6]),
])
def test_native_grid_uses_exact_python_geometry(width, gap, row_gap, spans, rtl):
    import _sfle_native
    slots = tuple(GridSlot(str(i), span) for i, span in enumerate(spans))
    heights = {slot.id: 10 + i * 7.125 for i, slot in enumerate(slots)}
    limits = {}
    rust = RustLayoutEngine(_sfle_native)
    python = PythonLayoutEngine()
    actual = compute_grid(slots, width, gap, row_gap,
                          heights, limits, rtl=rtl, engine=rust)
    expected = compute_grid(slots, width, gap, row_gap,
                            heights, limits, rtl=rtl, engine=python)
    assert actual == expected
    if not rtl:
        assert grid_widths(slots, width, gap, engine=rust) == (
            grid_widths(slots, width, gap, engine=python)
        )


def test_native_grid_seeded_randomized_exact_parity():
    import _sfle_native
    rng = random.Random(1359)
    rust = RustLayoutEngine(_sfle_native)
    python = PythonLayoutEngine()
    for _ in range(128):
        slots = tuple(
            GridSlot(str(i), rng.choice((1, 2, 3, 6, 12, "auto")),
                     offset=0, order=rng.randint(-2, 2))
            for i in range(rng.randint(1, 24))
        )
        width = rng.uniform(16, 1800)
        gap = rng.uniform(0, 9)
        row_gap = rng.uniform(0, 9)
        heights = {slot.id: rng.uniform(0, 50) for slot in slots}
        rtl = rng.choice((False, True))
        actual = compute_grid(slots, width, gap, row_gap, heights,
                              rtl=rtl, engine=rust)
        expected = compute_grid(slots, width, gap, row_gap, heights,
                                rtl=rtl, engine=python)
        assert actual == expected, (slots, width, gap, row_gap, rtl)
