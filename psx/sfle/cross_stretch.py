"""Resolved CSS cross-axis stretch for explicitly automatic cross sizes.

This kernel requires an established flex line cross size. It never treats
a definite item cross size as auto, nor invokes native measurement.
"""
from __future__ import annotations
from dataclasses import dataclass
from .flex_math import _number

@dataclass(frozen=True, slots=True)
class UsedCrossStretch:
    content_size: float
    border_size: float

def resolve_cross_stretch(
    line_cross_size: float,
    padding_border: float,
    start_margin: float,
    end_margin: float,
    *,
    min_content_size: float = 0.0,
    max_content_size: float | None = None,
) -> UsedCrossStretch:
    """Stretch auto cross content size, clamp content to definite min/max.

    CSS fixed padding and border cannot shrink. Negative available content
    floors at zero. If min exceeds max, min wins.
    """
    line = _number(line_cross_size, "line_cross_size")
    edges = _number(padding_border, "padding_border")
    start = _number(start_margin, "start_margin")
    end = _number(end_margin, "end_margin")
    minimum = _number(min_content_size, "min_content_size")
    maximum = None if max_content_size is None else _number(max_content_size, "max_content_size")
    if min(line, edges, minimum) < 0 or (maximum is not None and maximum < 0):
        raise ValueError("Line, edges and definite constraints must be nonnegative.")
    if maximum is not None:
        maximum = max(maximum, minimum)
    content = max(0.0, line - edges - start - end)
    content = max(content, minimum)
    if maximum is not None:
        content = min(content, maximum)
    return UsedCrossStretch(content, content + edges)
