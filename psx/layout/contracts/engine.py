"""Full numerical engine protocol for both independent Cinnamon backends.

This contract imports neither numerical implementation at module import time.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from psx.layout.contracts.capabilities import EngineCapabilities
from psx.layout.contracts.errors import SFLECapabilityError
from psx.layout.contracts.model import LayoutInput, LayoutResult
from psx.layout.grid.contracts import GridConstrainedRect, GridItemConstraints, GridSlot
from psx.layout.inline.semantic_inline_text import (
    InlineTextLayout, InlineTextMetrics, InlineTextSource,
)


class UnsupportedLayoutFeature(SFLECapabilityError):
    """Selected engine does not implement the requested capability."""


class LayoutEngine(Protocol):
    """Identical public operations, whether Rust or Python is selected."""

    backend_name: str

    @property
    def capabilities(self) -> EngineCapabilities: ...

    def compute(self, request: LayoutInput) -> LayoutResult: ...

    def compute_provisional(self, request: LayoutInput) -> LayoutResult: ...

    def compute_incremental(
        self, request: LayoutInput, *,
        previous_input: LayoutInput | None = None,
        previous_result: LayoutResult | None = None,
        native_measurement_invalidated: bool = False,
        reused_contexts: list[str] | None = None,
    ) -> LayoutResult: ...

    def compute_grid(
        self, slots: Sequence[GridSlot], content_width: float,
        column_gap: float = 0, row_gap: float = 0,
        item_heights: Mapping[str, float] | None = None,
        constraints: Mapping[str, GridItemConstraints] | None = None,
        *, rtl: bool = False,
    ) -> tuple[tuple[GridConstrainedRect, ...], ...]: ...

    def layout_inline_text(
        self, sources: Sequence[InlineTextSource], available_width: float,
        measure: Callable[[str, str], InlineTextMetrics], *,
        text_align: str = "left",
    ) -> InlineTextLayout: ...
