"""Renderer-neutral block formatting arithmetic for measured atomic boxes.

This module does not implement an inline formatting context or browser text
fragmentation. Mixed/inline flows must be rejected by the caller until the
corresponding formatting algorithm is certified.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fixed_point import LayoutUnit


@dataclass(frozen=True, slots=True)
class BlockItem:
    """A measured child border box and its resolved outer margins in CSS px."""

    width: float
    height: float
    margin_top: float = 0.0
    margin_right: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0


@dataclass(frozen=True, slots=True)
class BlockPlacement:
    x: float
    y: float
    width: float
    height: float


def layout_block_children(
    available_width: float,
    children: tuple[BlockItem, ...],
) -> tuple[BlockPlacement, ...]:
    """Place independent block-level border boxes in vertical normal flow.

    The given widths/heights are measured used border-box sizes. This stage
    handles positive and negative margins without claiming CSS margin collapse,
    auto inline margins, float avoidance or fragmentation. The caller must
    resolve those features first or report unsupported formatting.
    """
    def px(value: float) -> float:
        return LayoutUnit.from_nearest(value).to_px()

    if available_width < 0:
        raise ValueError("Available block inline size cannot be negative.")
    width = px(available_width)
    cursor = 0.0
    placements: list[BlockPlacement] = []
    for child in children:
        if child.width < 0 or child.height < 0:
            raise ValueError("Block border-box dimensions cannot be negative.")
        x = px(child.margin_left)
        y = px(cursor + child.margin_top)
        child_width = px(child.width)
        if x + child_width + px(child.margin_right) > width:
            # Overflow is legal in CSS. The containing block does not
            # silently shrink a measured fixed-size child.
            pass
        placements.append(BlockPlacement(x, y, child_width, px(child.height)))
        cursor = px(y + child.height + child.margin_bottom)
    return tuple(placements)
