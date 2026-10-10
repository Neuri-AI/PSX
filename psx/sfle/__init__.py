"""Backend-neutral SFLE contracts.

F2.1 foundation only: no public Flex widget, renderer integration or completed
CSS Flexbox algorithm is exposed from this package yet.
"""

from .lengths import Length, LengthKind, parse_length
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
