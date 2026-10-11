"""Used CSS box geometry without percentage/intrinsic resolution.

All edge values must have already been resolved into finite logical CSS
pixels by the caller. This module converts a positioned *margin box* to
border, padding and content rectangles without mutating VDOM/native widgets.

It is an intermediate geometry utility: margin collapse, auto margins,
box-sizing normalization and percentage reference rules are outside its scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flex_math import _number
from .fixed_point import LayoutUnit
from .model import BoxRect, Rect


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


def _inset(rect: Rect, edges: UsedEdges, name: str) -> Rect:
    width = (LayoutUnit.from_nearest(rect.width) - LayoutUnit.from_nearest(edges.horizontal)).to_px()
    height = (LayoutUnit.from_nearest(rect.height) - LayoutUnit.from_nearest(edges.vertical)).to_px()
    # CSS min sizing/box-sizing must already have produced a feasible
    # border-box. Do not silently shrink positive borders or padding.
    if width < 0 or height < 0:
        raise ValueError(f"{name} edges exceed their containing rectangle.")
    return Rect(
        (LayoutUnit.from_nearest(rect.x) + LayoutUnit.from_nearest(edges.left)).to_px(),
        (LayoutUnit.from_nearest(rect.y) + LayoutUnit.from_nearest(edges.top)).to_px(),
        width, height,
    )


def used_box_rect(margin_box: Rect, edges: UsedBoxEdges) -> BoxRect:
    """Return the four CSS rectangles from a physically positioned margin box.

    Signed margins are supported only when the *outer margin box* remains a
    representable nonnegative-size rectangle (as required by Rect). The
    upstream CSS layout algorithm must decide used widths and box-sizing.
    """

    if not isinstance(margin_box, Rect) or not isinstance(edges, UsedBoxEdges):
        raise TypeError("A margin Rect and UsedBoxEdges are required.")
    border = _inset(margin_box, edges.margin, "Margin")
    padding = _inset(border, edges.border, "Border")
    content = _inset(padding, edges.padding, "Padding")
    return BoxRect(content=content, padding=padding, border=border, margin=margin_box)
