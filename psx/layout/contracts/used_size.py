"""Shared immutable used-size tree for Rust/Python measurement planning.

The contract performs no numerical layout or native toolkit operations.
"""
from __future__ import annotations
from dataclasses import dataclass
from psx.layout.contracts.model import LayoutConstraints


@dataclass(frozen=True, slots=True)
class UsedSizeTree:
    generation: int
    content: tuple[tuple[str, LayoutConstraints], ...]
    deferred: tuple[str, ...]
