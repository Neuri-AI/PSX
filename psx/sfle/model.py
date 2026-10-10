"""Immutable, renderer-neutral layout data contracts.

These structures describe inputs and outputs. The CSS Flexbox computation
itself and the renderer measurement/geometry adapters are subsequent F2/F3
deliverables. No GUI package is imported here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .lengths import Length, LengthKind


def _finite(value: float | None, name: str) -> None:
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric or None.")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite.")


class WritingDirection(str, Enum):
    """Initial horizontal writing-mode inline direction."""

    LTR = "ltr"
    RTL = "rtl"


@dataclass(frozen=True, slots=True)
class AvailableSize:
    """A number and whether CSS considers the size definite.

    An indefinite size may carry a finite available-space hint. None is
    always indefinite; a definite size must have a numeric value.
    """

    value: float | None
    definite: bool

    def __post_init__(self) -> None:
        _finite(self.value, "AvailableSize.value")
        if not isinstance(self.definite, bool):
            raise TypeError("AvailableSize.definite must be bool.")
        if self.definite and self.value is None:
            raise ValueError("A definite size requires a numeric value.")
        if self.value is not None and self.value < 0:
            raise ValueError("Available size cannot be negative.")


@dataclass(frozen=True, slots=True)
class LayoutConstraints:
    """Constraint values to pass between measurement and computation."""

    width: AvailableSize
    height: AvailableSize


@dataclass(frozen=True, slots=True)
class BoxEdges:
    """CSS edges in top, right, bottom, left order (unresolved allowed)."""

    top: Length
    right: Length
    bottom: Length
    left: Length

    @classmethod
    def zero(cls) -> BoxEdges:
        zero = Length.px(0)
        return cls(zero, zero, zero, zero)


@dataclass(frozen=True, slots=True)
class Rect:
    """Floating-point top-left logical coordinates and box dimensions."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        for name in ("x", "y", "width", "height"):
            _finite(getattr(self, name), f"Rect.{name}")
        if self.width < 0 or self.height < 0:
            raise ValueError("Rect width and height must be nonnegative.")


@dataclass(frozen=True, slots=True)
class BoxRect:
    """Computed CSS boxes, deliberately separate from native widget handles."""

    content: Rect
    padding: Rect
    border: Rect
    margin: Rect


@dataclass(frozen=True, slots=True)
class IntrinsicSizes:
    """Renderer-measured intrinsic content metrics in logical pixels."""

    min_content_width: float
    max_content_width: float
    min_content_height: float
    max_content_height: float
    preferred_width: float
    preferred_height: float
    baseline: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "min_content_width", "max_content_width",
            "min_content_height", "max_content_height",
            "preferred_width", "preferred_height", "baseline",
        ):
            value = getattr(self, name)
            _finite(value, f"IntrinsicSizes.{name}")
            if value is not None and value < 0:
                raise ValueError(f"IntrinsicSizes.{name} must be nonnegative.")


@dataclass(frozen=True, slots=True)
class MeasuredBox:
    """Measurement with revision for cache/invalidation compatibility."""

    node_id: str
    intrinsic: IntrinsicSizes
    constraints: LayoutConstraints
    revision: int

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("MeasuredBox.node_id must not be empty.")
        if self.revision < 0:
            raise ValueError("MeasuredBox.revision must be nonnegative.")


@dataclass(frozen=True, slots=True)
class LayoutNode:
    """Tree node with serialized style pairs; no VNode or native handles."""

    node_id: str
    parent_id: str | None
    component: str
    style: tuple[tuple[str, Length | str | float | int], ...]

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("LayoutNode.node_id must not be empty.")
        if self.parent_id == self.node_id:
            raise ValueError("A layout node cannot be its own parent.")
        if not self.component:
            raise ValueError("LayoutNode.component must not be empty.")
        names = [name for name, _ in self.style]
        if len(names) != len(set(names)):
            raise ValueError("A layout style cannot contain duplicate property names.")
        for _, value in self.style:
            if isinstance(value, (int, float)):
                _finite(value, "LayoutNode.style numeric value")


@dataclass(frozen=True, slots=True)
class LayoutInput:
    """Snapshot contract shared by the Rust primary and Python fallback."""

    schema_version: int
    generation: int
    direction: WritingDirection
    constraints: LayoutConstraints
    nodes: tuple[LayoutNode, ...]
    measurements: tuple[MeasuredBox, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported SFLE input schema version.")
        if self.generation < 0:
            raise ValueError("Layout generation must be nonnegative.")
        if not isinstance(self.direction, WritingDirection):
            raise TypeError("LayoutInput.direction must be a WritingDirection.")
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Layout tree node IDs must be unique.")
        existing = set(ids)
        for node in self.nodes:
            if node.parent_id is not None and node.parent_id not in existing:
                raise ValueError(f"Missing parent for node {node.node_id!r}.")
        measured = [m.node_id for m in self.measurements]
        if len(measured) != len(set(measured)):
            raise ValueError("Layout measurements must have unique node IDs.")
        if not set(measured).issubset(existing):
            raise ValueError("Measurements must refer to nodes in the layout tree.")


@dataclass(frozen=True, slots=True)
class LayoutResult:
    """An eventual pure layout result. No algorithm is implemented here."""

    schema_version: int
    generation: int
    boxes: tuple[tuple[str, BoxRect], ...]
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported SFLE result schema version.")
        if self.generation < 0:
            raise ValueError("Layout result generation must be nonnegative.")
        ids = [node_id for node_id, _ in self.boxes]
        if len(ids) != len(set(ids)):
            raise ValueError("Layout results must have unique node IDs.")
