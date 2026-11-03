"""Cinnamon-neutral layout contracts, projection and runtime integration.

The optional Python numerical solver is intentionally NOT imported during
package initialization. Rust installations must be able to import and use
these contracts without the fallback package being present.
"""
from psx.layout.contracts.capabilities import EngineCapabilities, SCHEMA_VERSION
from psx.layout.contracts.engine import LayoutEngine, UnsupportedLayoutFeature
from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError, SFLEError, SFLEWireError
from psx.layout.contracts.lengths import Length, LengthKind, parse_length
from psx.layout.contracts.model import (
    AvailableSize, BoxEdges, BoxRect, IntrinsicSizes,
    LayoutConstraints, LayoutInput, LayoutNode, LayoutResult,
    MeasuredBox, Rect, WritingDirection,
)
from psx.layout.contracts.wire import (
    dumps_input, layout_input_from_wire, layout_input_to_wire,
    layout_result_from_wire, layout_result_to_wire, length_from_wire,
    length_to_wire, loads_input,
)

# Older callers may import the explicit fallback from
# psx.layout.fallback.engine; do not re-export it eagerly here.
__all__ = [
    "AvailableSize", "BoxEdges", "BoxRect", "DiagnosticCode",
    "EngineCapabilities", "IntrinsicSizes", "LayoutConstraints",
    "LayoutInput", "LayoutNode", "LayoutResult", "LayoutEngine", "Length",
    "LengthKind", "MeasuredBox", "Rect", "SCHEMA_VERSION",
    "SFLECapabilityError", "SFLEError", "SFLEWireError", "UnsupportedLayoutFeature",
    "WritingDirection", "dumps_input", "layout_input_from_wire",
    "layout_input_to_wire", "layout_result_from_wire",
    "layout_result_to_wire", "length_from_wire", "length_to_wire",
    "loads_input", "parse_length",
]

# Backward-compatible *explicit* symbols are resolved lazily. A mere
# import of psx.layout, markup or a Rust engine never loads the fallback.
_OPTIONAL_FALLBACK = frozenset({"PythonLayoutEngine"})
_OPTIONAL_WORKERS = frozenset({
    "ToolkitWorkerAdapter", "start_kivy_worker_layout", "start_tk_worker_layout",
})


def __getattr__(name: str):
    if name in _OPTIONAL_FALLBACK:
        from importlib import import_module
        return getattr(import_module("psx.layout.fallback.engine"), name)
    if name in _OPTIONAL_WORKERS:
        from importlib import import_module
        return getattr(import_module("psx.layout.runtime.toolkit_worker"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ += sorted(_OPTIONAL_FALLBACK | _OPTIONAL_WORKERS)
