"""Load-time SFLE Rust-primary negotiation with a deterministic Python fallback.

A missing native extension may select Python once. A loaded but incompatible
native extension is an error, not a fallback. Native compute failures are
never retried through Python inside the same layout transaction.
"""
from __future__ import annotations

import importlib
from collections import OrderedDict
from dataclasses import replace
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
        # Exact, bounded, backend-neutral solved-layout reuse. Most GridItem
        # children have a small immutable subtree; repeated viewport widths
        # should not re-cross PyO3 and solve every one of those contexts.
        # Never retain VNodes, native widgets, or renderer state here.
        self._exact_results: OrderedDict[tuple, LayoutResult] = OrderedDict()
        self._exact_limit = 4096
        self._exact_hits = 0
        self._exact_misses = 0

    def _exact_key(self, request: LayoutInput) -> tuple | None:
        # Large roots are already solved incrementally by Rust; avoid
        # allocating enormous keys (and retaining full result trees).
        if not request.nodes or len(request.nodes) > 24:
            return None
        key = (
            request.schema_version, request.direction, request.constraints,
            tuple((n.node_id, n.parent_id, n.component, n.style)
                  for n in request.nodes),
            tuple((m.node_id, m.intrinsic, m.constraints)
                  for m in request.measurements),
        )
        try:
            hash(key)
        except TypeError:
            return None
        return key

    def _exact_lookup(self, request: LayoutInput, *, enabled: bool = True) -> LayoutResult | None:
        if not enabled:
            return None
        key = self._exact_key(request)
        if key is None:
            return None
        result = self._exact_results.get(key)
        if result is None:
            self._exact_misses += 1
            return None
        self._exact_results.move_to_end(key)
        self._exact_hits += 1
        return replace(result, generation=request.generation, geometry_commit_error=None)

    def _exact_publish(self, request: LayoutInput, result: LayoutResult) -> None:
        if result.diagnostics or result.geometry_commit_error not in (None, 0.0):
            return
        key = self._exact_key(request)
        if key is None:
            return
        self._exact_results[key] = replace(result, geometry_commit_error=None)
        self._exact_results.move_to_end(key)
        while len(self._exact_results) > self._exact_limit:
            self._exact_results.popitem(last=False)

    @property
    def capabilities(self) -> EngineCapabilities:
        return rust_engine_capabilities(
            has_grid=callable(getattr(self._module, "compute_grid_json", None)),
            has_inline=callable(getattr(self._module, "compute_inline_text_json", None)),
            has_flow=callable(getattr(self._module, "compute_measured_flow_json", None)),
            has_recursive=callable(getattr(self._module, "compute_recursive_tree_json", None)),
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
        cached = self._exact_lookup(request)
        if cached is not None:
            return cached
        result = deserialize_response(
            self._module.compute_json(serialize_snapshot(request)), request
        )
        self._exact_publish(request, result)
        return result

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
        # Geometry is a pure function of the normalized contract. An exact
        # accepted snapshot is reusable across transaction generations even
        # when an intermediate resize visited a different width. Never bypass
        # the invalidated-native-measurement gate.
        cached = self._exact_lookup(
            request, enabled=not native_measurement_invalidated,
        )
        if cached is not None:
            if reused_contexts is not None and request.nodes:
                reused_contexts.append(request.nodes[0].node_id)
            return cached
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
        self._exact_publish(request, result)
        return result

    def compute_provisional(self, request: LayoutInput) -> LayoutResult:
        return deserialize_response(
            self._module.compute_provisional_json(serialize_snapshot(request)), request
        )

    def compute_grid(
        self, slots, content_width, column_gap=0, row_gap=0,
        item_heights=None, constraints=None, *, rtl=False,
    ):
        """Compute Grid through the real native Rust ABI."""
        import json
        from psx.layout.grid.contracts import GridConstrainedRect, GridPackingError
        from psx.layout.grid.solver import _validate_grid_input
        _validate_grid_input(
            slots, content_width, column_gap, row_gap,
            item_heights, constraints, rtl=rtl,
        )
        method = getattr(self._module, "compute_grid_json", None)
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

    def layout_inline_text(
        self, sources, available_width, measure, *, text_align="left",
    ):
        """Tokenize/measure shared text, solve native Rust fragment placement."""
        import math
        from psx.layout.inline.semantic_inline_text import (
            _measured_inline_atoms, InlineTextFragment, InlineTextLayout,
        )
        if not math.isfinite(available_width) or available_width < 0:
            raise ValueError("Inline containing width must be finite and nonnegative.")
        if text_align not in ("left", "right", "center"):
            raise ValueError("Unsupported inline text alignment.")
        response = self.compute_inline_text({
            "width": available_width,
            "text_align": text_align,
            "atoms": _measured_inline_atoms(sources, measure),
        })
        fragments = tuple(
            InlineTextFragment(**part) for part in response["fragments"]
        )
        return InlineTextLayout(
            fragments, response["width"], response["height"],
            response["line_count"],
        )

    def layout_block_children(self, available_width, children):
        """Measured normal Block flow directly in the Rust kernel."""
        from psx.layout.flow.solver import layout_block_children
        return layout_block_children(available_width, children, engine=self)

    def layout_inline_atoms(self, available_width, atoms):
        """Measured atomic Inline flow directly in the Rust kernel."""
        from psx.layout.flow.solver import layout_inline_atoms
        return layout_inline_atoms(available_width, atoms, engine=self)

    def compute_recursive_tree(
        self, nodes, *, generation, writing=None, auto_cross=(),
    ):
        """Run the independently compiled Rust recursive layout kernel."""
        from dataclasses import asdict
        from enum import Enum
        import json
        from psx.layout.contracts.model import Rect, WritingDirection
        from psx.layout.contracts.recursive_tree import (
            MarginFlexBox, MarginTreeLayout, MarginTreeNode,
        )
        if writing is None:
            writing = WritingDirection.LTR
        if type(generation) is not int or generation < 0:
            raise ValueError("generation must be a nonnegative integer.")
        if not isinstance(writing, WritingDirection):
            raise TypeError("writing must be WritingDirection.")
        if not isinstance(nodes, tuple) or any(
            not isinstance(node, MarginTreeNode) for node in nodes
        ):
            raise TypeError("nodes must be tuple[MarginTreeNode, ...].")
        module = self._module
        native = getattr(module, "compute_recursive_tree_json", None)
        if not callable(native):
            raise SFLEError(
                DiagnosticCode.BACKEND_MISMATCH,
                "The selected Rust Cinnamon wheel lacks recursive geometry ABI.",
            )
        payload = {
            "generation": generation,
            "writing": writing.value,
            "nodes": [asdict(node) for node in nodes],
            "auto_cross": [item.node_id for item in auto_cross],
        }
        # Explicit serializer of enums preserves the original typed contract.
        def serialize(value: object):
            if isinstance(value, Enum):
                return value.value
            raise TypeError(f"Unsupported recursive wire value: {type(value).__name__}")

        try:
            wire = json.dumps(payload, default=serialize, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT,
                f"Invalid recursive geometry snapshot: {exc}",
            ) from exc
        try:
            result = json.loads(native(wire))
        except (ValueError, TypeError) as exc:
            raise SFLEError(
                DiagnosticCode.INVALID_TREE,
                f"Native recursive geometry rejected the tree: {exc}",
            ) from exc
        if not isinstance(result, dict) or result.get("generation") != generation:
            raise SFLEError(
                DiagnosticCode.BACKEND_MISMATCH,
                "Rust recursive geometry returned an invalid generation.",
            )
        def rect(data):
            return Rect(data["x"], data["y"], data["width"], data["height"])

        # Fixed (non-auto) CSS margins are *inputs*, not computed layout sizes.
        # A serde_json float roundtrip can change the shortest binary rendering by
        # one ULP; the historical Python API preserves the exact supplied value.
        # Leave auto margins and every coordinate to the real native Rust solver.
        source_items = {
            node.node_id: node.item for node in nodes if node.item is not None
        }
        def used_margin(box, side):
            item = source_items.get(box["node_id"])
            if item is not None:
                declared = getattr(item, side).value
                if declared is not None:
                    return declared
            return box["used_" + side + "_margin"]

        try:
            boxes = tuple(MarginFlexBox(
                box["node_id"], rect(box["content"]), rect(box["padding"]),
                rect(box["border"]), used_margin(box, "main_start"),
                used_margin(box, "main_end"), box["line_index"],
                box["used_cross_start_margin"], box["used_cross_end_margin"],
            ) for box in result["boxes"])
        except (TypeError, KeyError, ValueError) as exc:
            raise SFLEError(
                DiagnosticCode.BACKEND_MISMATCH,
                "Rust recursive geometry returned malformed rectangles.",
            ) from exc
        if tuple(b.node_id for b in boxes) != tuple(n.node_id for n in nodes):
            raise SFLEError(
                DiagnosticCode.BACKEND_MISMATCH,
                "Rust recursive geometry changed tree ordering or identities.",
            )
        return MarginTreeLayout(generation, boxes)



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
