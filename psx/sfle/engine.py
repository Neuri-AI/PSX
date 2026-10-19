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

    backend_name = "python"

    @property
    def capabilities(self) -> EngineCapabilities:
        return CONTRACT_ONLY_CAPABILITIES

    def compute(self, request: LayoutInput) -> LayoutResult:
        from .compute_alpha import compute_snapshot
        return compute_snapshot(request)

    def compute_incremental(
        self,
        request: LayoutInput,
        *,
        previous_input: LayoutInput | None = None,
        previous_result: LayoutResult | None = None,
        native_measurement_invalidated: bool = False,
    ) -> LayoutResult:
        """Reuse certified identical input, otherwise run the full solver.

        Partial subtree solving is deliberately not claimed here. This
        opt-in method does not modify the shared Rust/Python engine protocol.
        """
        from .context_invalidation_plan import plan_context_invalidation
        from .incremental_result_reuse import reuse_unchanged_layout
        plan = plan_context_invalidation(previous_input, request)
        # Partial recomputation requires a solver-supported context receipt.
        # Until then, changes to any dependency must use full computation.
        if plan.full_recompute or plan.dirty_nodes:
            return self.compute(request)
        cached = reuse_unchanged_layout(
            previous_input, previous_result, request,
            native_measurement_invalidated=native_measurement_invalidated,
        )
        return cached if cached is not None else self.compute(request)

    def compute_provisional(self, request: LayoutInput) -> LayoutResult:
        """Noncommittable geometry used solely to obtain post-flex widths."""
        from .compute_alpha import compute_snapshot
        return compute_snapshot(request, provisional=True)

    def compute_grid(
        self,
        slots,
        content_width,
        column_gap=0,
        row_gap=0,
        item_heights=None,
        constraints=None,
        *,
        rtl=False,
    ):
        """Pure Cinnamon Grid math integration; native mounting remains G3."""
        from .grid_math import compute_grid
        return compute_grid(
            slots, content_width, column_gap, row_gap, item_heights,
            constraints, rtl=rtl,
        )
