"""F2.2.4 definite used-size preparation for recursive Flex containers.

A resolved content-box size is NOT the final flex-distributed size. This
restricted step establishes dimensions only when CSS specified lengths have
definite references and already-resolved padding/borders. Auto, intrinsic,
and cyclic percentage axes remain explicitly unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constraint_propagation import ChildSizing, resolve_child_constraints
from .model import AvailableSize, LayoutConstraints
from .percentage_box_sizing import BoxSizing, normalize_box_size
from .sizing import ResolutionKind


@dataclass(frozen=True, slots=True)
class UsedContentResolution:
    """Content sizes suitable as descendant references only on definite axes."""

    content: LayoutConstraints
    width_kind: ResolutionKind
    height_kind: ResolutionKind


def resolve_used_content_size(
    parent_content: LayoutConstraints,
    sizing: ChildSizing,
    *,
    box_sizing: BoxSizing,
    horizontal_padding_border: float = 0.0,
    vertical_padding_border: float = 0.0,
) -> UsedContentResolution:
    """Resolve known specified sizes to CSS used content-box dimensions.

    Does not implement auto, flex distribution, automatic minimums, intrinsic
    sizing or constraint cycles. Unresolved axes carry no definite number.
    """
    if not isinstance(box_sizing, BoxSizing):
        raise TypeError("box_sizing must be BoxSizing.")
    specified = resolve_child_constraints(parent_content, sizing)

    def axis(value: AvailableSize, edges: float) -> AvailableSize:
        # Validate edge widths even when the specified axis is indefinite.
        normalized = normalize_box_size(0.0, edges, box_sizing)
        if not value.definite:
            return AvailableSize(None, False)
        assert value.value is not None
        return AvailableSize(
            normalize_box_size(value.value, normalized.padding_border, box_sizing).content,
            True,
        )

    return UsedContentResolution(
        LayoutConstraints(
            axis(specified.constraints.width, horizontal_padding_border),
            axis(specified.constraints.height, vertical_padding_border),
        ),
        specified.width_kind,
        specified.height_kind,
    )
