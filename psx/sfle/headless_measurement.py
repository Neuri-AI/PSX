"""Deterministic headless intrinsic measurement adapter for SFLE.

Measurements are provided by a test host as immutable intrinsic snapshots.
They are not inferred from CSS available-space hints. The common native-round
handshake still validates generation, revision and effective constraints.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort


@dataclass(frozen=True, slots=True)
class HeadlessMeasurementSource:
    """Immutable map of node IDs to host-supplied intrinsic size snapshots."""

    snapshots: tuple[tuple[str, IntrinsicSizes], ...]

    def __post_init__(self) -> None:
        ids: set[str] = set()
        for node_id, intrinsic in self.snapshots:
            if not isinstance(node_id, str) or not node_id or node_id in ids:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Duplicate or empty headless node ID.")
            if not isinstance(intrinsic, IntrinsicSizes):
                raise TypeError("Headless snapshots must contain IntrinsicSizes.")
            ids.add(node_id)

    def measure(self, request: MeasurementRequest) -> MeasuredBox:
        """Return host-supplied metrics under exactly the requested constraints."""
        if not isinstance(request, MeasurementRequest):
            raise TypeError("Expected MeasurementRequest.")
        for node_id, intrinsic in self.snapshots:
            if node_id == request.node_id:
                return MeasuredBox(node_id, intrinsic, request.constraints, request.revision)
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            f"No headless intrinsic snapshot for {request.node_id!r}.",
        )

    def port(self) -> NativeMeasurementPort:
        """Expose the common synchronous protocol; headless has no GUI thread."""
        return NativeMeasurementPort(lambda: True, self.measure)
