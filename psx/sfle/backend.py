"""Load-time SFLE Rust-primary negotiation with a deterministic Python fallback.

A missing native extension may select Python once. A loaded but incompatible
native extension is an error, not a fallback. Native compute failures are
never retried through Python inside the same layout transaction.
"""
from __future__ import annotations

import importlib
from types import ModuleType

from .capabilities import CONTRACT_ONLY_CAPABILITIES
from .engine import PythonLayoutEngine
from .errors import DiagnosticCode, SFLEError
from .model import LayoutInput, LayoutResult
from .native_wire import serialize_snapshot, serialize_result, deserialize_response


class RustLayoutEngine:
    """PyO3-backed engine that passes only validated, immutable snapshots."""

    backend_name = "rust"

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @property
    def capabilities(self):
        return CONTRACT_ONLY_CAPABILITIES

    def compute(self, request: LayoutInput) -> LayoutResult:
        # Mixed Block/Flex contexts share one flow compositor, while each
        # nested Flex context is solved by this Rust engine.
        from psx.markup.html_aliases import FORMATTING_TAGS
        if (request.nodes and request.nodes[0].component in FORMATTING_TAGS
                and any(node.component == "Flex" for node in request.nodes[1:])):
            from .measured_block_snapshot import compute_measured_block_snapshot
            return compute_measured_block_snapshot(request, flex_engine=self)
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
    ) -> LayoutResult:
        """Use native optional incremental ABI when a safe prior result exists."""
        native = getattr(self._module, "compute_incremental_json", None)
        if (native_measurement_invalidated or previous_input is None
                or previous_result is None or not callable(native)):
            return self.compute(request)
        return deserialize_response(
            native(
                serialize_snapshot(request),
                serialize_snapshot(previous_input),
                serialize_result(previous_result),
            ), request,
        )

    def compute_provisional(self, request: LayoutInput) -> LayoutResult:
        return deserialize_response(
            self._module.compute_provisional_json(serialize_snapshot(request)), request
        )


def load_layout_engine() -> RustLayoutEngine | PythonLayoutEngine:
    """Select once before computation; runtime errors propagate unchanged."""
    try:
        native = importlib.import_module("_sfle_native")
    except (ImportError, OSError):
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
