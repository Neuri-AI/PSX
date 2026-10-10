"""Backend-neutral SFLE contracts.

F2.1 foundation only: no public Flex widget, renderer integration or completed
CSS Flexbox algorithm is exposed from this package yet.
"""

from .capabilities import EngineCapabilities, SCHEMA_VERSION
from .engine import LayoutEngine, PythonLayoutEngine, UnsupportedLayoutFeature
from .errors import DiagnosticCode, SFLECapabilityError, SFLEError, SFLEWireError
from .lengths import Length, LengthKind, parse_length
from .wire import (
    dumps_input,
    layout_input_from_wire,
    layout_input_to_wire,
    layout_result_from_wire,
    layout_result_to_wire,
    length_from_wire,
    length_to_wire,
    loads_input,
)
from .model import (
    AvailableSize,
    BoxEdges,
    BoxRect,
    IntrinsicSizes,
    LayoutConstraints,
    LayoutInput,
    LayoutNode,
    LayoutResult,
    MeasuredBox,
    Rect,
    WritingDirection,
)

__all__ = [
    "AvailableSize",
    "DiagnosticCode",
    "EngineCapabilities",
    "LayoutEngine",
    "PythonLayoutEngine",
    "SCHEMA_VERSION",
    "SFLECapabilityError",
    "SFLEError",
    "SFLEWireError",
    "UnsupportedLayoutFeature",
    "dumps_input",
    "loads_input",
    "layout_input_from_wire",
    "layout_input_to_wire",
    "layout_result_from_wire",
    "layout_result_to_wire",
    "length_from_wire",
    "length_to_wire",
    "BoxEdges",
    "BoxRect",
    "IntrinsicSizes",
    "LayoutConstraints",
    "LayoutInput",
    "LayoutNode",
    "LayoutResult",
    "Length",
    "LengthKind",
    "MeasuredBox",
    "Rect",
    "WritingDirection",
    "parse_length",
]
