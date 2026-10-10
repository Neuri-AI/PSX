"""Pure SFLE computation interface (Rust primary; Python parity fallback).

F2.1 declares capability negotiation without pretending that CSS Flexbox
computation already works. Engine loading and runtime selection follow only
after a conformant Rust or Python implementation exists.
"""

from __future__ import annotations

from typing import Protocol

from .capabilities import CONTRACT_ONLY_CAPABILITIES, EngineCapabilities
from .errors import DiagnosticCode, SFLECapabilityError
from .model import LayoutInput, LayoutResult


class UnsupportedLayoutFeature(SFLECapabilityError):
    """The selected engine does not implement a CSS layout capability."""


class LayoutEngine(Protocol):
    """Pure, renderer-neutral engine interface shared by Rust and Python."""

    @property
    def capabilities(self) -> EngineCapabilities:
        """Declare supported CSS features using the versioned manifest."""
        ...

    def compute(self, request: LayoutInput) -> LayoutResult:
        """Compute a complete layout or raise an explicit capability error."""
        ...


class PythonLayoutEngine:
    """Internal fail-closed experimental snapshot coordinator (not advertised)."""

    @property
    def capabilities(self) -> EngineCapabilities:
        return CONTRACT_ONLY_CAPABILITIES

    def compute(self, request: LayoutInput) -> LayoutResult:
        from .compute_alpha import compute_snapshot
        return compute_snapshot(request)
