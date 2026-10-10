"""Resolved first-baseline alignment using supplied, measured metrics."""
from __future__ import annotations
from dataclasses import dataclass
from .flex_math import _number

@dataclass(frozen=True, slots=True)
class BaselineItem:
    border_cross_size: float
    start_margin: float
    end_margin: float
    baseline: float

    def __post_init__(self) -> None:
        for name in ("border_cross_size", "start_margin", "end_margin", "baseline"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.border_cross_size < 0 or not 0 <= self.baseline <= self.border_cross_size:
            raise ValueError("Baseline offset must fit the border box.")

@dataclass(frozen=True, slots=True)
class BaselineGroup:
    ascent: float
    descent: float

    @property
    def extent(self) -> float:
        return self.ascent + self.descent

def measure_baseline_group(items: tuple[BaselineItem, ...]) -> BaselineGroup:
    if not isinstance(items, tuple) or not items or any(
        not isinstance(item, BaselineItem) for item in items
    ):
        raise ValueError("A nonempty tuple of measured baseline items is required.")
    return BaselineGroup(
        max(item.start_margin + item.baseline for item in items),
        max(item.end_margin + item.border_cross_size - item.baseline for item in items),
    )

def position_baseline_item(
    item: BaselineItem, group: BaselineGroup, line_cross_size: float,
    *, cross_forward: bool = True,
) -> float:
    if not isinstance(item, BaselineItem) or not isinstance(group, BaselineGroup):
        raise TypeError("Expected BaselineItem and BaselineGroup.")
    if type(cross_forward) is not bool:
        raise TypeError("cross_forward must be bool.")
    line = _number(line_cross_size, "line_cross_size")
    if line < 0:
        raise ValueError("Negative line cross size.")
    logical = group.ascent - item.baseline
    return logical if cross_forward else line - logical - item.border_cross_size
