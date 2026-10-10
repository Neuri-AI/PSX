"""F2.2.4.5 intrinsic leaf-size *suggestions* for dependency resolution.

The preferred intrinsic size is NOT a flex item's final used CSS size.
Flex basis, min/max, available space and CSS auto sizing are resolved by the
layout algorithm later. No unsupported cyclic percentage is coerced to AUTO.
"""
from __future__ import annotations
from dataclasses import dataclass

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .model import LayoutInput
from .sizing import ResolutionKind
from .used_size_tree import UsedSizeTree


@dataclass(frozen=True, slots=True)
class LeafAutoSizing:
    node_id: str
    width_kind: ResolutionKind
    height_kind: ResolutionKind


@dataclass(frozen=True, slots=True)
class IntrinsicLeafSuggestion:
    """Preferred intrinsic contributions; not authoritative CSS used dimensions."""
    node_id: str
    preferred_width: float | None
    preferred_height: float | None


def collect_leaf_intrinsic_suggestions(
    snapshot: LayoutInput,
    used: UsedSizeTree,
    *,
    declarations: tuple[LeafAutoSizing, ...],
    revisions: tuple[tuple[str, int], ...] = (),
) -> tuple[IntrinsicLeafSuggestion, ...]:
    """Read current-revision native intrinsic contributions for AUTO leaves.

    Fails closed on AUTO containers and indefinite percentages rather than
    applying a preferred intrinsic size as if CSS Flex had allocated it.
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
    expected_revisions: dict[str, int] = {}
    for node_id, revision in revisions:
        if node_id not in ids or node_id in expected_revisions or type(revision) is not int or revision < 0:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Invalid measurement revision.")
        expected_revisions[node_id] = revision
    measured = {m.node_id: m for m in snapshot.measurements}
    suggestions = []
    for node_id, constraints in used.content:
        declaration = by_id.get(node_id)
        if declaration is None:
            continue
        need_width = declaration.width_kind == ResolutionKind.AUTO and not constraints.width.definite
        need_height = declaration.height_kind == ResolutionKind.AUTO and not constraints.height.definite
        if (need_width or need_height) and node_id in parent_ids:
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Auto container size requires CSS child contributions.", node_id)
        if ((declaration.width_kind == ResolutionKind.UNRESOLVED_PERCENT and not constraints.width.definite)
                or (declaration.height_kind == ResolutionKind.UNRESOLVED_PERCENT and not constraints.height.definite)):
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Indefinite percentage requires CSS cyclic sizing phase.", node_id)
        measurement = measured.get(node_id)
        if (need_width or need_height) and measurement is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Missing intrinsic measurement.", node_id)
        if (need_width or need_height) and (
            measurement.constraints != constraints or measurement.revision != expected_revisions.get(node_id, 0)
        ):
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale intrinsic measurement constraints or revision.", node_id)
        if need_width or need_height:
            suggestions.append(IntrinsicLeafSuggestion(
                node_id,
                measurement.intrinsic.preferred_width if need_width else None,
                measurement.intrinsic.preferred_height if need_height else None,
            ))
    return tuple(suggestions)
