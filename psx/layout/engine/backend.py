"""Load-time SFLE Rust-primary negotiation with a deterministic Python fallback.

A missing native extension may select Python once. A loaded but incompatible
native extension is an error, not a fallback. Native compute failures are
never retried through Python inside the same layout transaction.
"""
from __future__ import annotations

import importlib
from types import ModuleType

from psx.layout.contracts.capabilities import EngineCapabilities, rust_engine_capabilities
from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.contracts.model import LayoutInput, LayoutResult
from psx.layout.contracts.native_wire import serialize_snapshot, serialize_result, deserialize_response


class RustLayoutEngine:
    """PyO3-backed engine that passes only validated, immutable snapshots."""

    backend_name = "rust"

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @property
    def capabilities(self) -> EngineCapabilities:
        return rust_engine_capabilities(
            has_grid=callable(getattr(self._module, "compute_grid_json", None)),
            has_inline=callable(getattr(self._module, "compute_inline_text_json", None)),
        )

    def compute_inline_text(self, payload: dict[str, object]) -> dict[str, object]:
        """Use the Rust numeric inline layout kernel; never silently fall back."""
        import json
        native = getattr(self._module, "compute_inline_text_json", None)
        if not callable(native):
            raise SFLEError(
                DiagnosticCode.BACKEND_MISMATCH,
                "Loaded Rust Cinnamon extension lacks compute_inline_text_json; "
                "rebuild _sfle_native from the current PSX branch.",
            )
        wire = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        response = json.loads(native(wire))
        if not isinstance(response, dict) or not all(
            key in response for key in ("fragments", "width", "height", "line_count")
        ):
            raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                            "Invalid Rust inline fragment response.")
        return response

    def compute(self, request: LayoutInput) -> LayoutResult:
        # Rust owns the entire layout computation, including semantic
        # Block/Inline roots via flow_snapshot.rs. Never call the Python
        # measured-block compositor from the Rust engine facade.
        return deserialize_response(
            self._module.compute_json(serialize_snapshot(request)), request
        )

    def compute_incremental(
        self,
        request: LayoutInput,
        *,
        previous_input: LayoutInput | None = None,
        previous_result: LayoutResult | None = None,
        native_measurement_invalidated: bool = False,
        reused_contexts: list[str] | None = None,
    ) -> LayoutResult:
        """Use native optional incremental ABI when a safe prior result exists."""
        native = getattr(self._module, "compute_incremental_json", None)
        if (native_measurement_invalidated or previous_input is None
                or previous_result is None or not callable(native)):
            return self.compute(request)
        payload = native(
            serialize_snapshot(request),
            serialize_snapshot(previous_input),
            serialize_result(previous_result),
        )
        result = deserialize_response(payload, request)
        if reused_contexts is not None:
            import json
            trace = json.loads(payload).get("reused_contexts")
            if (not isinstance(trace, list) or
                    any(not isinstance(value, str) for value in trace)):
                raise SFLEError(
                    DiagnosticCode.BACKEND_MISMATCH,
                    "Rust Cinnamon wheel lacks validated incremental-reuse telemetry.",
                )
            reused_contexts.extend(trace)
        return result

    def compute_provisional(self, request: LayoutInput) -> LayoutResult:
        return deserialize_response(
            self._module.compute_provisional_json(serialize_snapshot(request)), request
        )

    def compute_grid(
        self, slots, content_width, column_gap=0, row_gap=0,
        item_heights=None, constraints=None, *, rtl=False,
    ):
        """Compute Grid using this engine's actual native PyO3 ABI."""
        from psx.layout.grid.solver import compute_grid
        return compute_grid(
            slots, content_width, column_gap, row_gap, item_heights,
            constraints, rtl=rtl, engine=self,
        )

    def layout_inline_text(
        self, sources, available_width, measure, *, text_align="left",
    ):
        """Compute text geometry with Rust's independent numerical kernel."""
        from psx.layout.inline.semantic_inline_text import layout_inline_text
        return layout_inline_text(
            sources, available_width, measure,
            text_align=text_align, engine=self,
        )


def load_layout_engine() -> RustLayoutEngine | object:
    """Select once before computation; runtime errors propagate unchanged."""
    try:
        native = importlib.import_module("_sfle_native")
    except (ImportError, OSError):
        # The Python solver is load-time optional. Never import it in a
        # process that successfully selected the native Rust engine.
        try:
            from psx.layout.fallback.engine import PythonLayoutEngine
        except ModuleNotFoundError as exc:
            if exc.name in ("psx.layout.fallback", "psx.layout.fallback.engine"):
                raise SFLEError(
                    DiagnosticCode.BACKEND_MISMATCH,
                    "No Cinnamon engine available: _sfle_native is absent and "
                    "the optional Python fallback is not installed.",
                ) from exc
            raise
        return PythonLayoutEngine()
    required = ("schema_version", "compute_json", "compute_provisional_json")
    if any(not callable(getattr(native, name, None)) for name in required):
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Native SFLE extension is missing mandatory v1 ABI functions.")
    try:
        version = native.schema_version()
    except Exception as exc:
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Unable to negotiate native SFLE ABI.") from exc
    if type(version) is not int or version != 1:
        raise SFLEError(DiagnosticCode.BACKEND_MISMATCH,
                        "Native SFLE ABI version differs from Python schema 1.")
    return RustLayoutEngine(native)
