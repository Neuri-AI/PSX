"""Immutable, versioned SFLE engine capability declaration.

The manifest advertises what an engine can actually compute, not the eventual
target CSS Flexbox feature set. The initial contract-only phase advertises no
supported layout features.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLECapabilityError

SCHEMA_VERSION = 1

KNOWN_FEATURES = frozenset({
    "direction_row", "direction_column", "direction_reverse",
    "writing_ltr", "writing_rtl", "gap", "grow_shrink",
    "wrapping", "multi_line_alignment", "intrinsic_sizing",
    "percentage_sizing", "auto_margins", "baseline_alignment",
    "min_max_constraints", "overflow",
})


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    """Feature manifest compatible with either computation backend."""

    engine_name: str
    schema_version: int
    features: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.engine_name, str) or not self.engine_name:
            raise ValueError("Capability engine_name must be a nonempty string.")
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("Unsupported SFLE capability schema version.")
        if not isinstance(self.features, frozenset):
            raise TypeError("Capability features must be a frozenset.")
        if not all(isinstance(feature, str) and feature in KNOWN_FEATURES
                   for feature in self.features):
            raise ValueError("Unrecognized SFLE capability feature.")

    def require(self, feature: str) -> None:
        if feature not in KNOWN_FEATURES or feature not in self.features:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"SFLE engine {self.engine_name!r} does not support {feature!r}.",
            )


CONTRACT_ONLY_CAPABILITIES = EngineCapabilities(
    engine_name="python-contract-only",
    schema_version=SCHEMA_VERSION,
    features=frozenset(),
)
