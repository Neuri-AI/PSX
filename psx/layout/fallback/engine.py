"""Pure SFLE computation interface (Rust primary; Python parity fallback).

F2.1 declares capability negotiation without pretending that CSS Flexbox
computation already works. Engine loading and runtime selection follow only
after a conformant Rust or Python implementation exists.
"""

from __future__ import annotations


from psx.layout.contracts.capabilities import PYTHON_CAPABILITIES, EngineCapabilities
from psx.layout.contracts.engine import LayoutEngine, UnsupportedLayoutFeature
from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError
from psx.layout.contracts.model import LayoutInput, LayoutResult


class PythonLayoutEngine:
    """Internal fail-closed experimental snapshot coordinator (not advertised)."""

    backend_name = "python"

    @property
    def capabilities(self) -> EngineCapabilities:
        return PYTHON_CAPABILITIES

    def compute(self, request: LayoutInput) -> LayoutResult:
        if not isinstance(request, LayoutInput):
            raise TypeError("Expected immutable LayoutInput.")
        # Rust and Python must consume the same semantic flow snapshot wire.
        from psx.markup.html_aliases import FORMATTING_TAGS
        if request.nodes and request.nodes[0].component in FORMATTING_TAGS:
            from psx.layout.fallback.measured_block_snapshot import compute_measured_block_snapshot
            return compute_measured_block_snapshot(request, flex_engine=self)
        from psx.layout.fallback.compute_alpha import compute_snapshot
        return compute_snapshot(request)

    def compute_incremental(
        self,
        request: LayoutInput,
        *,
        previous_input: LayoutInput | None = None,
        previous_result: LayoutResult | None = None,
        native_measurement_invalidated: bool = False,
        reused_contexts: list[str] | None = None,
    ) -> LayoutResult:
        """Reuse unchanged snapshots or safely isolated Flex sizing subtrees.

        When context reuse is ineligible, perform a complete solve. Geometry
        placement always runs through Cinnamon's normal compositor.
        """
        from psx.markup.html_aliases import FORMATTING_TAGS
        if request.nodes and request.nodes[0].component in FORMATTING_TAGS:
            # Conservative complete flow reflow until fragment-level dependency
            # tracking is certified. Stable VNode identity stays with the caller.
            return self.compute(request)
        from psx.layout.runtime.context_invalidation_plan import plan_context_invalidation
        from psx.layout.runtime.incremental_result_reuse import reuse_unchanged_layout
        plan = plan_context_invalidation(previous_input, request)
        if plan.full_recompute or native_measurement_invalidated:
            return self.compute(request)
        if plan.dirty_nodes:
            from psx.layout.fallback.compute_alpha import compute_snapshot
            return compute_snapshot(
                request, previous_input=previous_input,
                previous_result=previous_result, reused_contexts=reused_contexts,
            )
        cached = reuse_unchanged_layout(
            previous_input, previous_result, request,
            native_measurement_invalidated=native_measurement_invalidated,
        )
        return cached if cached is not None else self.compute(request)

    def compute_provisional(self, request: LayoutInput) -> LayoutResult:
        """Noncommittable geometry used solely to obtain post-flex widths."""
        from psx.markup.html_aliases import FORMATTING_TAGS
        if request.nodes and request.nodes[0].component in FORMATTING_TAGS:
            return self.compute(request)
        from psx.layout.fallback.compute_alpha import compute_snapshot
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
        # The common adapter validates the same inputs for Rust and Python.
        # It routes back into the standalone Python algorithm without recursion.
        from psx.layout.grid.solver import compute_grid
        return compute_grid(
            slots, content_width, column_gap, row_gap, item_heights,
            constraints, rtl=rtl, engine=self,
        )

    def layout_inline_text(
        self, sources, available_width, measure, *, text_align="left",
    ):
        """Compute fragments with the independent Python numerical kernel."""
        from psx.layout.fallback.semantic_inline_text import python_layout_inline_text
        return python_layout_inline_text(
            sources, available_width, measure, text_align=text_align,
        )
    def layout_block_children(self, available_width, children):
        from psx.layout.flow.solver import layout_block_children
        return layout_block_children(available_width, children, engine=self)

    def layout_inline_atoms(self, available_width, atoms):
        from psx.layout.flow.solver import layout_inline_atoms
        return layout_inline_atoms(available_width, atoms, engine=self)

    def compute_recursive_tree(
        self, nodes, *, generation, writing=None, auto_cross=(),
    ):
        """Run independent Python recursive numerical geometry."""
        from psx.layout.contracts.model import WritingDirection
        from psx.layout.runtime.recursive_geometry import compute_margin_tree
        return compute_margin_tree(
            nodes, generation=generation,
            writing=WritingDirection.LTR if writing is None else writing,
            auto_cross=auto_cross, engine=self,
        )

