"""Backend-neutral SFLE contracts.

F2.1 foundation only: no public Flex widget, renderer integration or completed
CSS Flexbox algorithm is exposed from this package yet.
"""

from psx.layout.contracts.capabilities import EngineCapabilities, SCHEMA_VERSION
from psx.layout.fallback.engine import LayoutEngine, PythonLayoutEngine, UnsupportedLayoutFeature
from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError, SFLEError, SFLEWireError
from psx.layout.contracts.lengths import Length, LengthKind, parse_length
from psx.layout.contracts.wire import (
    dumps_input,
    layout_input_from_wire,
    layout_input_to_wire,
    layout_result_from_wire,
    layout_result_to_wire,
    length_from_wire,
    length_to_wire,
    loads_input,
)
from psx.layout.contracts.model import (
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
from psx.layout.runtime.toolkit_worker import (
    ToolkitWorkerAdapter,
    start_kivy_worker_layout,
    start_tk_worker_layout,
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
    "ToolkitWorkerAdapter",
    "start_kivy_worker_layout",
    "start_tk_worker_layout",
]
