"""Rust-primary Cinnamon Grid math entry point.

Native width allocations and final rectangles are calculated by _sfle_native
when the selected Cinnamon engine is Rust. The optional Python solver is
imported ONLY when Python was explicitly selected because native is absent.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from psx.layout.grid.contracts import (
    GridSlot, GridItemConstraints, GridConstrainedRect, GridPackingError,
)


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
    backend = getattr(engine, "backend_name", None)
    if backend == "python":
        from psx.layout.fallback.grid_math import compute_grid as python_compute_grid
        return python_compute_grid(
            slots, content_width, column_gap, row_gap, item_heights,
            constraints, rtl=rtl,
        )
    if backend != "rust":
        raise TypeError("Cinnamon Grid requires a RustLayoutEngine or PythonLayoutEngine.")
    method = getattr(getattr(engine, "_module", None), "compute_grid_json", None)
    if not callable(method):
        from psx.layout.contracts.errors import SFLEError, DiagnosticCode
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Cinnamon Rust wheel lacks the mandatory Grid ABI.")
    payload = {
        "items": [
            {"id": s.id, "span": s.span, "offset": s.offset, "order": s.order}
            for s in slots
        ],
        "width": content_width,
        "column_gap": column_gap,
        "row_gap": row_gap,
        "heights": dict(item_heights or {}),
        "constraints": {
            key: {
                "min_width": value.min_width,
                "max_width": value.max_width,
                "min_height": value.min_height,
                "max_height": value.max_height,
            }
            for key, value in (constraints or {}).items()
        },
        "rtl": rtl,
    }
    try:
        raw = json.loads(method(json.dumps(payload, allow_nan=False)))
        return tuple(tuple(GridConstrainedRect(**cell) for cell in row) for row in raw)
    except (TypeError, ValueError, KeyError) as exc:
        raise GridPackingError(f"Cinnamon Rust Grid result is invalid: {exc}") from exc


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
