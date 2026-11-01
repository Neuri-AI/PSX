"""Shared Cinnamon engine protocol; independent of either numerical solver."""
from __future__ import annotations
from typing import Protocol

from psx.layout.contracts.capabilities import EngineCapabilities
from psx.layout.contracts.errors import SFLECapabilityError
from psx.layout.contracts.model import LayoutInput, LayoutResult


class UnsupportedLayoutFeature(SFLECapabilityError):
    """The explicitly selected engine does not support a layout capability."""


class LayoutEngine(Protocol):
    """Renderer-neutral contract implemented independently by Rust and Python."""

    @property
    def capabilities(self) -> EngineCapabilities:
        ...

    def compute(self, request: LayoutInput) -> LayoutResult:
        ...
