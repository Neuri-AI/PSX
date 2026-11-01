"""Cinnamon-neutral layout contracts, projection and runtime integration.

The optional Python numerical solver is intentionally NOT imported during
package initialization. Rust installations must be able to import and use
these contracts without the fallback package being present.
"""
from psx.layout.contracts.capabilities import EngineCapabilities, SCHEMA_VERSION
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
    "LayoutInput", "LayoutNode", "LayoutResult", "Length",
    "LengthKind", "MeasuredBox", "Rect", "SCHEMA_VERSION",
    "SFLECapabilityError", "SFLEError", "SFLEWireError",
    "WritingDirection", "dumps_input", "layout_input_from_wire",
    "layout_input_to_wire", "layout_result_from_wire",
    "layout_result_to_wire", "length_from_wire", "length_to_wire",
    "loads_input", "parse_length",
]
