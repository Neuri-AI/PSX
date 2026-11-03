"""Backend-neutral records for measured block and atomic inline placement."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BlockItem:
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

@dataclass(frozen=True, slots=True)
class InlineAtom:
    width: float
    height: float
    baseline: float
