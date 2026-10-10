"""F2.2.4.5 immutable remeasurement round handshake.

Pure planning/acceptance only. The coordinator does not execute toolkit calls;
the UI-thread adapter fulfills the returned requests outside SFLE.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .measurement_plan import MeasurementRequest, accept_measurement
from .model import LayoutConstraints, LayoutInput, MeasuredBox
from .remeasurement import RemeasurementDelta


@dataclass(frozen=True, slots=True)
class MeasurementRound:
    generation: int
    requests: tuple[MeasurementRequest, ...]
    retained: tuple[MeasuredBox, ...]
    deferred: tuple[str, ...]


def prepare_round(
    snapshot: LayoutInput,
    delta: RemeasurementDelta,
    *,
    constraints: tuple[tuple[str, LayoutConstraints], ...],
    revisions: tuple[tuple[str, int], ...] = (),
) -> MeasurementRound:
    """Prepare a single measurement round from explicit, current constraints.

    Never fill unknown axes from ancestor available sizes. Revised or affected
    nodes must be measured; unaffected cached snapshots are retained only with
    identical constraints and revisions.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(delta, RemeasurementDelta):
        raise TypeError("Expected LayoutInput and RemeasurementDelta.")
    if delta.generation != snapshot.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale measurement delta.")
    ids = tuple(node.node_id for node in snapshot.nodes)
    known = set(ids)
    if len(set(delta.remeasure)) != len(delta.remeasure) or not set(delta.remeasure).issubset(known):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid remeasurement IDs.")
    if len(set(delta.deferred)) != len(delta.deferred) or not set(delta.deferred).issubset(known):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid deferred IDs.")
    values: dict[str, LayoutConstraints] = {}
    versions: dict[str, int] = {}
    for node_id, value in constraints:
        if node_id not in known or node_id in values or not isinstance(value, LayoutConstraints):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid/duplicate constraints.")
        values[node_id] = value
    for node_id, version in revisions:
        if node_id not in known or node_id in versions or type(version) is not int or version < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid/duplicate revision.")
        versions[node_id] = version
    if set(values) != known:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Missing measurement constraints.")
    for node_id in delta.deferred:
        if values[node_id].width.definite and values[node_id].height.definite:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Deferred node has fully definite constraints.")
    affected = set(delta.remeasure)
    cached = {item.node_id: item for item in snapshot.measurements}
    requests = []
    retained = []
    for node in reversed(snapshot.nodes):
        node_id = node.node_id
        constraint = values[node_id]
        revision = versions.get(node_id, 0)
        old = cached.get(node_id)
        if node_id not in affected and old is not None and old.constraints == constraint and old.revision == revision:
            retained.append(old)
        else:
            requests.append(MeasurementRequest(node_id, constraint, snapshot.generation, revision))
    return MeasurementRound(snapshot.generation, tuple(requests), tuple(retained), delta.deferred)


def accept_round(
    round_: MeasurementRound,
    measurements: tuple[MeasuredBox, ...],
    *,
    current_generation: int,
) -> tuple[MeasuredBox, ...]:
    """Atomically validate a full round before exposing any measured results."""
    if not isinstance(round_, MeasurementRound) or not isinstance(measurements, tuple):
        raise TypeError("Expected MeasurementRound and tuple of measurements.")
    if round_.generation != current_generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale measurement round.")
    provided = {}
    for measured in measurements:
        if not isinstance(measured, MeasuredBox) or measured.node_id in provided:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Duplicate/invalid measurement.")
        provided[measured.node_id] = measured
    expected = {request.node_id for request in round_.requests}
    if set(provided) != expected:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Incomplete or unexpected measurement round.")
    accepted = tuple(accept_measurement(
        request, provided[request.node_id], current_generation=current_generation,
    ) for request in round_.requests)
    return round_.retained + accepted
