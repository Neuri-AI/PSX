"""Logical parent identity used when committing solved native rectangles.

A renderer must not need a Python Flex solver's MarginTreeNode type merely
to translate its node_id and parent_id. Geometry is owned by the selected
Rust or Python engine; this type carries no numerical solver state.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LayoutTreeIdentity:
    node_id: str
    parent_id: str | None
    width: float = 0.0
    height: float = 0.0
