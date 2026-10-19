"""Fail-closed incremental Cinnamon result reuse.

This does not implement partial Flex solving. It avoids a full solver call
only if the *entire* immutable input (except generation bookkeeping) is
semantically equal to the previously committed input. Ownership remains
with the caller, which must discard both values after unmount/invalidation.
"""
from __future__ import annotations

from dataclasses import replace

from .model import LayoutInput, LayoutResult


def reuse_unchanged_layout(
    previous_input: LayoutInput | None,
    previous_result: LayoutResult | None,
    current_input: LayoutInput,
    *,
    native_measurement_invalidated: bool = False,
) -> LayoutResult | None:
    """Return a newly versioned result only for an identical complete input.

    Measurement revision fields are intentionally NOT ignored: a new revision
    might represent changed native font, theme, DPI, or resource metrics.
    Callers must also pass the explicit semantic native invalidation fence.
    """
    if native_measurement_invalidated or previous_input is None or previous_result is None:
        return None
    if previous_result.schema_version != current_input.schema_version:
        return None
    if previous_result.generation != previous_input.generation:
        return None
    if previous_input.schema_version != current_input.schema_version:
        return None
    if previous_input.constraints != current_input.constraints:
        return None
    if previous_input.direction != current_input.direction:
        return None
    if previous_input.nodes != current_input.nodes:
        return None
    if len(previous_input.measurements) != len(current_input.measurements):
        return None
    # Unlike simply comparing measurements, a revision increment is relevant.
    for old, new in zip(previous_input.measurements, current_input.measurements):
        if old.node_id != new.node_id or old.intrinsic != new.intrinsic:
            return None
        if old.constraints != new.constraints or old.revision != new.revision:
            return None
    if {node.node_id for node in current_input.nodes} != {key for key, _ in previous_result.boxes}:
        return None
    # A prior result that includes diagnostics or an incomplete geometry
    # transaction is not safe to reuse as a certified committed result.
    if previous_result.diagnostics or previous_result.geometry_commit_error not in (None, 0):
        return None
    return replace(previous_result, generation=current_input.generation)
