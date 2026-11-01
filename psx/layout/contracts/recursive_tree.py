"""Immutable historical recursive Flex input and output contracts.

All data classes and enum identities live here; the optional Python numerical
engine re-exports these exact objects. This module never imports the fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math

from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.contracts.fixed_point import LayoutUnit
from psx.layout.contracts.lengths import Length
from psx.layout.contracts.model import Rect, IntrinsicSizes, WritingDirection

def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return float(value)

def _clamp(value: float, minimum: float, maximum: float | None) -> float:
    return max(minimum, min(value, maximum)) if maximum is not None else max(minimum, value)


@dataclass(frozen=True, slots=True)
class FlexBasis:
    """Already-resolved main-axis sizes for one item in a single line.

    `basis` is the flex base size. `hypothetical` is the precomputed
    hypothetical main size after min/max clamps. Min/max must be used
    content-box lengths, not unresolved CSS expressions.
    """

    basis: float
    hypothetical: float
    grow: float = 0.0
    shrink: float = 1.0
    min_size: float = 0.0
    max_size: float | None = None

    def __post_init__(self) -> None:
        for name in ("basis", "hypothetical", "grow", "shrink", "min_size"):
            value = _number(getattr(self, name), f"FlexBasis.{name}")
            if value < 0:
                raise ValueError(f"FlexBasis.{name} cannot be negative.")
            object.__setattr__(self, name, value)
        if self.max_size is not None:
            limit = _number(self.max_size, "FlexBasis.max_size")
            if limit < self.min_size:
                raise ValueError("FlexBasis.max_size cannot be below min_size.")
            object.__setattr__(self, "max_size", limit)
        expected = _clamp(self.basis, self.min_size, self.max_size)
        if not math.isclose(self.hypothetical, expected, rel_tol=0, abs_tol=1e-9):
            raise ValueError(
                "FlexBasis.hypothetical must be the min/max-clamped basis. "
                "Resolve CSS intrinsic/auto constraints before invoking this kernel."
            )


class FlexDirection(str, Enum):
    ROW = "row"
    ROW_REVERSE = "row-reverse"
    COLUMN = "column"
    COLUMN_REVERSE = "column-reverse"


class FlexWrap(str, Enum):
    NOWRAP = "nowrap"
    WRAP = "wrap"
    WRAP_REVERSE = "wrap-reverse"


@dataclass(frozen=True, slots=True)
class UsedEdges:
    """Physical edges in top/right/bottom/left order, in logical CSS px."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def __post_init__(self) -> None:
        for name in ("top", "right", "bottom", "left"):
            object.__setattr__(self, name, _number(getattr(self, name), name))

    @property
    def horizontal(self) -> float:
        return (LayoutUnit.from_nearest(self.left) + LayoutUnit.from_nearest(self.right)).to_px()

    @property
    def vertical(self) -> float:
        return (LayoutUnit.from_nearest(self.top) + LayoutUnit.from_nearest(self.bottom)).to_px()


@dataclass(frozen=True, slots=True)
class UsedBoxEdges:
    """Resolved margin/padding/border widths; margin may be signed."""

    margin: UsedEdges = UsedEdges()
    border: UsedEdges = UsedEdges()
    padding: UsedEdges = UsedEdges()

    def __post_init__(self) -> None:
        if not all(isinstance(edges, UsedEdges) for edges in
                   (self.margin, self.border, self.padding)):
            raise TypeError("UsedBoxEdges requires UsedEdges instances.")
        if any(edge < 0 for edges in (self.border, self.padding)
               for edge in (edges.top, edges.right, edges.bottom, edges.left)):
            raise ValueError("Used padding and border widths cannot be negative.")


@dataclass(frozen=True, slots=True)
class UsedMargin:
    """A signed fixed CSS margin, or None for an auto margin."""

    value: float | None = 0.0

    def __post_init__(self) -> None:
        if self.value is not None:
            object.__setattr__(self, "value", _number(self.value, "margin"))


class CrossAlign(str, Enum):
    AUTO = "auto"
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    STRETCH = "stretch"
    BASELINE = "baseline"


class JustifyContent(str, Enum):
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"


class AlignContent(str, Enum):
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"
    STRETCH = "stretch"


@dataclass(frozen=True, slots=True)
class MarginFlexItem:
    node_id: str
    flex: FlexBasis
    cross_content_size: float
    edges: UsedBoxEdges = UsedBoxEdges()
    main_start: UsedMargin = UsedMargin()
    main_end: UsedMargin = UsedMargin()
    order: int = 0
    cross_start: UsedMargin = UsedMargin()
    cross_end: UsedMargin = UsedMargin()
    align_self: CrossAlign = CrossAlign.AUTO
    cross_size_auto: bool = False
    min_cross_content_size: float = 0.0
    max_cross_content_size: float | None = None
    baseline_from_cross_start: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("node_id must be nonempty.")
        if not isinstance(self.flex, FlexBasis) or not isinstance(self.edges, UsedBoxEdges):
            raise TypeError("flex and edges must be normalized.")
        if any(not isinstance(margin, UsedMargin) for margin in (
            self.main_start, self.main_end, self.cross_start, self.cross_end
        )):
            raise TypeError("margins must be UsedMargin.")
        if not isinstance(self.align_self, CrossAlign):
            raise TypeError("align_self must be CrossAlign.")
        if type(self.cross_size_auto) is not bool:
            raise TypeError("cross_size_auto must be bool.")
        minimum = _number(self.min_cross_content_size, "min_cross_content_size")
        maximum = (None if self.max_cross_content_size is None else
                   _number(self.max_cross_content_size, "max_cross_content_size"))
        if minimum < 0 or (maximum is not None and maximum < 0):
            raise ValueError("Cross size constraints must be nonnegative.")
        if self.baseline_from_cross_start is not None:
            baseline = _number(self.baseline_from_cross_start, "baseline_from_cross_start")
            if not 0 <= baseline <= _number(self.cross_content_size, 'cross_content_size'):
                raise ValueError("Measured baseline must lie within cross content size.")
        if self.edges.margin != UsedEdges():
            raise ValueError("Set all physical margins to zero; use main_start/main_end.")
        if type(self.order) is not int:
            raise TypeError("order must be a signed integer.")
        size = _number(self.cross_content_size, "cross_content_size")
        if size < 0:
            raise ValueError("cross size cannot be negative.")
        object.__setattr__(self, "cross_content_size", size)


@dataclass(frozen=True, slots=True)
class MarginFlexBox:
    node_id: str
    content: Rect
    padding: Rect
    border: Rect
    used_main_start_margin: float
    used_main_end_margin: float
    line_index: int
    used_cross_start_margin: float = 0.0
    used_cross_end_margin: float = 0.0


@dataclass(frozen=True, slots=True)
class MarginFlexLayout:
    lines: tuple[tuple[str, ...], ...]
    boxes: tuple[MarginFlexBox, ...]


@dataclass(frozen=True, slots=True)
class MarginTreeNode:
    node_id: str
    parent_id: str | None
    width: float
    height: float
    item: MarginFlexItem | None = None
    edges: UsedBoxEdges = UsedBoxEdges()
    direction: FlexDirection = FlexDirection.ROW
    wrap: FlexWrap = FlexWrap.NOWRAP
    main_gap: float = 0.0
    cross_gap: float = 0.0
    justify: JustifyContent = JustifyContent.FLEX_START
    align_items: CrossAlign = CrossAlign.FLEX_START
    align_content: AlignContent = AlignContent.FLEX_START
    intrinsic_basis: IntrinsicFlexInput | None = None


@dataclass(frozen=True, slots=True)
class MarginTreeLayout:
    generation: int
    boxes: tuple[MarginFlexBox, ...]


class MainAxis(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class OverflowMode(str, Enum):
    VISIBLE = "visible"
    CLIP = "clip"
    HIDDEN = "hidden"
    AUTO = "auto"
    SCROLL = "scroll"


@dataclass(frozen=True, slots=True)
class IntrinsicFlexInput:
    """Premeasured content-box sizes and CSS main-axis sizing decisions.

    width/height are *already definite used content sizes* if provided.
    `scroll_container` is a result from the overflow/scroll-container stage;
    the enum alone cannot determine whether `overflow:auto` scrolls.
    """

    intrinsic: IntrinsicSizes
    axis: MainAxis
    flex_basis: Length
    grow: float = 0.0
    shrink: float = 1.0
    preferred_main_size: float | None = None
    max_main_size: float | None = None
    min_main_size: float | None = None
    overflow: OverflowMode = OverflowMode.VISIBLE
    scroll_container: bool = False
    aspect_ratio: float | None = None
    preferred_cross_size: float | None = None
    replaced: bool = False
    # Compatibility hint; typed ratio and intrinsic cross metrics are authoritative.
    has_aspect_ratio_transfer: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.intrinsic, IntrinsicSizes):
            raise TypeError("intrinsic must be IntrinsicSizes.")
        if not isinstance(self.axis, MainAxis) or not isinstance(self.flex_basis, Length):
            raise TypeError("axis and flex_basis must be typed.")
        if not isinstance(self.overflow, OverflowMode):
            raise TypeError("overflow must be OverflowMode.")
        if (type(self.scroll_container) is not bool or type(self.replaced) is not bool
                or type(self.has_aspect_ratio_transfer) is not bool):
            raise TypeError("scroll, replaced, and aspect-ratio flags must be bool.")
        if self.scroll_container and self.overflow not in (OverflowMode.AUTO, OverflowMode.SCROLL):
            raise ValueError("Scroll container flag requires auto or scroll overflow.")
        if self.overflow == OverflowMode.SCROLL and not self.scroll_container:
            raise ValueError("scroll overflow must be marked as a scroll container.")
        for name in ("grow", "shrink", "preferred_main_size", "max_main_size", "min_main_size"):
            value = getattr(self, name)
            if value is None:
                continue
            numeric = _number(value, name)
            if numeric < 0:
                raise ValueError(f"{name} must be nonnegative.")
            object.__setattr__(self, name, numeric)
        if self.aspect_ratio is not None:
            ratio = _number(self.aspect_ratio, "aspect_ratio")
            if ratio <= 0:
                raise ValueError("aspect_ratio must be positive.")
            object.__setattr__(self, "aspect_ratio", ratio)
        if self.preferred_cross_size is not None:
            cross = _number(self.preferred_cross_size, "preferred_cross_size")
            if cross < 0:
                raise ValueError("preferred_cross_size must be nonnegative.")
            object.__setattr__(self, "preferred_cross_size", cross)
        if self.max_main_size is not None and self.min_main_size is not None:
            if self.max_main_size < self.min_main_size:
                raise ValueError("max_main_size cannot be below min_main_size.")


@dataclass(frozen=True, slots=True)
class IntrinsicLeafStyle:
    node_id: str
    flex_basis: Length
    main_size: float | None = None
    min_main_size: float | None = None
    max_main_size: float | None = None
    cross_size_auto: bool = True


@dataclass(frozen=True, slots=True)
class AutoCrossSize:
    node_id: str
