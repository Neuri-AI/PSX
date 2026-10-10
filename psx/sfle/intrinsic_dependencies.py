"""F2.2.4.5 explicit intrinsic leaf-size dependency resolution.

Only non-replaced measured leaves with no children may resolve an AUTO
content dimension from their recorded preferred intrinsic size. This is a
restricted layout phase, not a CSS flex item final-size computation. An
indefinite percentage is NOT interchangeable with AUTO.
"""
from __future__ import annotations
from dataclasses import dataclass

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .model import AvailableSize, LayoutConstraints, LayoutInput
from .sizing import ResolutionKind
from .used_size_tree import UsedSizeTree


@dataclass(frozen=True, slots=True)
class LeafAutoSizing:
    node_id: str
    width_kind: ResolutionKind
    height_kind: ResolutionKind


def resolve_measured_auto_leaves(
    snapshot: LayoutInput,
    used: UsedSizeTree,
    *,
    declarations: tuple[LeafAutoSizing, ...],
) -> UsedSizeTree:
    """Resolve AUTO on measured leaves; fail closed on non-leaves/cycles.

    Measurements are trusted only when captured under the same constraints
    and current revisions supplied in LayoutInput. CSS automatic container
    sizing, cross-axis stretch and flex distribution remain later phases.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(used, UsedSizeTree):
        raise TypeError("Expected LayoutInput and UsedSizeTree.")
    if snapshot.generation != used.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale used-size generation.")
    ids = tuple(n.node_id for n in snapshot.nodes)
    if tuple(n for n, _ in used.content) != ids:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Used tree ordering mismatch.")
    if not isinstance(declarations, tuple):
        raise TypeError("Declarations must be a tuple.")
    parent_ids = {n.parent_id for n in snapshot.nodes if n.parent_id is not None}
    by_id = {}
    for declaration in declarations:
        if not isinstance(declaration, LeafAutoSizing):
            raise TypeError("Expected LeafAutoSizing.")
        if declaration.node_id not in ids or declaration.node_id in by_id:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Unknown or duplicate declaration.")
        if not isinstance(declaration.width_kind, ResolutionKind) or not isinstance(declaration.height_kind, ResolutionKind):
            raise TypeError("Expected ResolutionKind axes.")
        by_id[declaration.node_id] = declaration
    measured = {m.node_id: m for m in snapshot.measurements}
    updated = []
    for node_id, constraints in used.content:
        declaration = by_id.get(node_id)
        if declaration is None:
            updated.append((node_id, constraints))
            continue
        if node_id in parent_ids and (
            declaration.width_kind == ResolutionKind.AUTO or declaration.height_kind == ResolutionKind.AUTO
        ):
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto sizing of containers requires CSS child contributions.", node_id)
        measurement = measured.get(node_id)
        def axis(value: AvailableSize, kind: ResolutionKind, preferred: float) -> AvailableSize:
            if kind == ResolutionKind.AUTO and not value.definite:
                if measurement is None:
                    raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Missing intrinsic measurement.", node_id)
                return AvailableSize(preferred, True)
            if kind == ResolutionKind.UNRESOLVED_PERCENT and not value.definite:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Indefinite percentage requires CSS cyclic sizing phase.", node_id)
            return value
        updated.append((node_id, LayoutConstraints(
            axis(constraints.width, declaration.width_kind, measurement.intrinsic.preferred_width if measurement else 0),
            axis(constraints.height, declaration.height_kind, measurement.intrinsic.preferred_height if measurement else 0),
        )))
    return UsedSizeTree(used.generation, tuple(updated), tuple(
        id for id, c in updated if not c.width.definite or not c.height.definite
    ))
