"""Shared F2 measurement test adapters; no geometry expectations here."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sfle'))

from psx.sfle.model import BoxRect, IntrinsicSizes, LayoutResult, Rect
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.remeasure_session import compute_with_width_measurements
from test_f2_acceptance_contract_red import case_snapshot
from test_sfle_f2_differential import _rust_compute


def _rect(data: dict[str, float]) -> Rect:
    return Rect(data["x"], data["y"], data["width"], data["height"])


def rust_compute(rust_binary, snapshot) -> LayoutResult:
    data = _rust_compute(rust_binary, snapshot)
    assert data["ok"], f"Rust compute error: {data.get('error')}"
    result = data["result"]
    return LayoutResult(
        result["schema_version"],
        result["generation"],
        tuple(
            (
                box["node_id"],
                BoxRect(
                    _rect(box["content"]), _rect(box["padding"]),
                    _rect(box["border"]), _rect(box["margin"]),
                ),
            )
            for box in result["boxes"]
        ),
    )


def run_measured_case(case_id: str, backend: str, rust_binary, *,
                      characters_px: int, initial_widths: dict[str, float]):
    """Send identical initial snapshots and width-dependent callbacks to both engines."""
    snapshot = replace(case_snapshot(case_id), measurements=())
    compute = (
        PythonLayoutEngine().compute if backend == "python"
        else lambda request: rust_compute(rust_binary, request)
    )
    calls: list[tuple[str, float]] = []

    def measure_fn(node_id: str, width: float) -> IntrinsicSizes:
        calls.append((node_id, width))
        height = math.ceil(characters_px / width) * 20
        return IntrinsicSizes(
            0, characters_px, 20, height,
            initial_widths[node_id], height,
        )

    result = compute_with_width_measurements(
        snapshot, compute, measure_fn, initial_widths=initial_widths,
    )
    return dict(result.boxes), calls
