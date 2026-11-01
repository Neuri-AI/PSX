"""Versioned, bounded Cinnamon layout capability declarations.

These identifiers represent finite numerical kernel contracts, not full CSS or
browser conformance. Feature maturity and optional Rust ABI presence are explicit.
"""
from __future__ import annotations

from dataclasses import dataclass

from psx.layout.contracts.errors import DiagnosticCode, SFLECapabilityError

SCHEMA_VERSION = 1

KNOWN_FEATURES = frozenset({
    "direction_row", "direction_column", "direction_reverse",
    "writing_ltr", "writing_rtl", "gap", "grow_shrink",
    "wrapping", "multi_line_alignment", "intrinsic_sizing",
    "percentage_sizing", "auto_margins", "baseline_alignment",
    "min_max_constraints", "overflow",
    "block_flow_measured", "inline_flow_measured",
    "grid_12_columns", "inline_text_ltr_normal",
    "full_layout_compute", "provisional_layout_compute",
    "incremental_layout_compute", "width_dependent_remeasurement",
    "measured_flow_primitives",
})

FEATURE_SCOPES = {
    "block_flow_measured": "Normal flow of measured block boxes (bounded grammar)",
    "inline_flow_measured": "Measured atomic inline boxes (not full text shaping)",
    "grid_12_columns": "PSX 12-column Grid packing and allocation",
    "inline_text_ltr_normal": "Source-preserving LTR white-space:normal fragments",
    "full_layout_compute": "Immutable snapshot computation and failure diagnostics",
    "provisional_layout_compute": "Provisional geometry for intrinsic measurement",
    "incremental_layout_compute": "Safe recomputation/reuse with prior snapshot",
    "width_dependent_remeasurement": "Finite width-dependent UI measurement rounds",
    "measured_flow_primitives": "Measured atomic Block/Inline placements without text shaping",
}


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    """Implemented and independently certified features of one engine."""

    engine_name: str
    schema_version: int
    features: frozenset[str]
    certified_features: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.engine_name, str) or not self.engine_name:
            raise ValueError("Capability engine_name must be a nonempty string.")
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("Unsupported SFLE capability schema version.")
        if not isinstance(self.features, frozenset):
            raise TypeError("Capability features must be a frozenset.")
        if not all(isinstance(f, str) and f in KNOWN_FEATURES for f in self.features):
            raise ValueError("Unrecognized SFLE capability feature.")
        if not isinstance(self.certified_features, frozenset):
            raise TypeError("Certified capability features must be a frozenset.")
        if not self.certified_features.issubset(self.features):
            raise ValueError("Certified features must be implemented features.")

    def status(self, feature: str) -> str:
        """Report 'certified', 'implemented', or 'unsupported'."""
        if feature in self.certified_features:
            return "certified"
        if feature in self.features:
            return "implemented"
        return "unsupported"

    def require(self, feature: str) -> None:
        if self.status(feature) == "unsupported":
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"SFLE engine {self.engine_name!r} does not support {feature!r}.",
            )


# Historical constant retained, never returned by a running solver.
CONTRACT_ONLY_CAPABILITIES = EngineCapabilities(
    engine_name="python-contract-only", schema_version=SCHEMA_VERSION,
    features=frozenset(),
)

# Advertise only bounded implementations with exercised acceptance fixtures.
_COMMON_IMPLEMENTED = frozenset({
    "direction_row", "direction_column", "direction_reverse",
    "writing_ltr", "gap", "grow_shrink", "wrapping",
    "intrinsic_sizing", "percentage_sizing", "min_max_constraints",
    "block_flow_measured", "inline_flow_measured",
    "full_layout_compute", "provisional_layout_compute",
    "incremental_layout_compute", "width_dependent_remeasurement",
})
_COMMON_CERTIFIED = frozenset({
    "direction_row", "direction_column", "direction_reverse",
    "gap", "wrapping", "min_max_constraints",
    "block_flow_measured", "inline_flow_measured",
    "full_layout_compute", "provisional_layout_compute",
    "incremental_layout_compute", "width_dependent_remeasurement",
})
_OPTIONAL = frozenset({"grid_12_columns", "inline_text_ltr_normal", "measured_flow_primitives"})

PYTHON_CAPABILITIES = EngineCapabilities(
    engine_name="python", schema_version=SCHEMA_VERSION,
    features=_COMMON_IMPLEMENTED | _OPTIONAL,
    certified_features=_COMMON_CERTIFIED | _OPTIONAL,
)


def rust_engine_capabilities(*, has_grid: bool, has_inline: bool, has_flow: bool = False) -> EngineCapabilities:
    """Expose optional numerical kernels only if the Rust wheel has their ABI."""
    optional = frozenset(
        name for name, present in (
            ("grid_12_columns", has_grid),
            ("inline_text_ltr_normal", has_inline),
            ("measured_flow_primitives", has_flow),
        ) if present
    )
    return EngineCapabilities(
        engine_name="rust", schema_version=SCHEMA_VERSION,
        features=_COMMON_IMPLEMENTED | optional,
        certified_features=_COMMON_CERTIFIED | optional,
    )
