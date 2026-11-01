"""Measured atomic Block/Inline dispatch: independent Rust and Python kernels."""
from __future__ import annotations
import json
import math
from psx.layout.contracts.flow import BlockItem, BlockPlacement, InlineAtom
from psx.layout.contracts.errors import DiagnosticCode, SFLEError

def _validate_flow(kind: str, width: float, items: tuple[object, ...]) -> None:
    """One immutable input grammar for two independent numerical solvers."""
    if isinstance(width, bool) or not isinstance(width, (float, int)) or not math.isfinite(width):
        raise ValueError("Available measured-flow width must be finite.")
    if width < 0:
        raise ValueError("Available measured-flow width cannot be negative.")
    if not isinstance(items, tuple):
        raise TypeError("Measured-flow items must be an immutable tuple.")
    expected = BlockItem if kind == "block" else InlineAtom
    for item in items:
        if not isinstance(item, expected):
            raise TypeError(f"Expected {expected.__name__} measured-flow item.")
        values = (
            (item.width, item.height, item.margin_top, item.margin_right,
             item.margin_bottom, item.margin_left)
            if kind == "block"
            else (item.width, item.height, item.baseline)
        )
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in values):
            raise ValueError("Measured-flow geometry must contain finite numeric metrics.")
        if item.width < 0 or item.height < 0:
            raise ValueError("Measured-flow border boxes must be nonnegative.")
        if kind == "inline" and not 0 <= item.baseline <= item.height:
            raise ValueError("Invalid atomic inline baseline.")


def _native(mode: str, width: float, objects: tuple[object, ...], engine):
    entry = getattr(getattr(engine, "_module", None), "compute_measured_flow_json", None)
    if not callable(entry):
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Rust Cinnamon wheel lacks the measured-flow ABI.")
    if mode == "block":
        items = [
            {"width": v.width, "height": v.height, "margin_top": v.margin_top,
             "margin_right": v.margin_right, "margin_bottom": v.margin_bottom,
             "margin_left": v.margin_left} for v in objects
        ]
    else:
        items = [
            {"width": v.width, "height": v.height, "baseline": v.baseline}
            for v in objects
        ]
    payload = json.dumps({"mode": mode, "available_width": width, "items": items},
                         allow_nan=False)
    result = json.loads(entry(payload))
    if not isinstance(result, list) or len(result) != len(objects):
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Invalid Rust measured-flow placement count.")
    try:
        return tuple(BlockPlacement(**placement) for placement in result)
    except (TypeError, ValueError, KeyError) as exc:
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Invalid Rust measured-flow geometry.") from exc

def layout_block_children(
    available_width: float, children: tuple[BlockItem, ...], *,
    engine: object | None = None,
) -> tuple[BlockPlacement, ...]:
    _validate_flow("block", available_width, children)
    if engine is None:
        from psx.layout.engine.backend import load_layout_engine
        engine = load_layout_engine()
    backend = getattr(engine, "backend_name", None)
    if backend == "rust":
        return _native("block", available_width, children, engine)
    if backend == "python":
        from psx.layout.fallback.flow_layout import layout_block_children as compute
        return compute(available_width, children)
    raise TypeError("Expected Cinnamon Rust or Python engine.")

def layout_inline_atoms(
    available_width: float, atoms: tuple[InlineAtom, ...], *,
    engine: object | None = None,
) -> tuple[BlockPlacement, ...]:
    _validate_flow("inline", available_width, atoms)
    if engine is None:
        from psx.layout.engine.backend import load_layout_engine
        engine = load_layout_engine()
    backend = getattr(engine, "backend_name", None)
    if backend == "rust":
        return _native("inline", available_width, atoms, engine)
    if backend == "python":
        from psx.layout.fallback.flow_layout import layout_inline_atoms as compute
        return compute(available_width, atoms)
    raise TypeError("Expected Cinnamon Rust or Python engine.")
