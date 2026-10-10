"""Pure calculation boundary for the future Rust primary / Python fallback.

F2.1 exposes the protocol and an explicit unsupported-feature failure, not
an inaccurate partial implementation of CSS Flexbox.
"""

from __future__ import annotations

from typing import Protocol

from .model import LayoutInput, LayoutResult


class UnsupportedLayoutFeature(RuntimeError):
    """A layout capability was requested before its normative implementation."""


class LayoutEngine(Protocol):
    """Both Rust and Python implementations must honor this same protocol."""

    def compute(self, request: LayoutInput) -> LayoutResult:
        """Compute a complete, deterministic layout or fail explicitly."""
        ...


class PythonLayoutEngine:
    """Fallback placeholder: computation is deliberately not implemented yet."""

    def compute(self, request: LayoutInput) -> LayoutResult:
        raise UnsupportedLayoutFeature(
            "SFLE Flexbox calculation has not been implemented; "
            "F2.1 currently defines input/output contracts only."
        )
