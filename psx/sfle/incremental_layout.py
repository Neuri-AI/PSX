"""Fail-closed incremental Cinnamon coordinator.

Only byte-for-byte equivalent *semantic* immutable snapshots may reuse a
complete result. The planner's dirty Flex contexts are advisory until engines
implement certified partial subtree computation. This module stores no VNodes,
native handles or callbacks and never mutates the pure computation contract.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from .model import LayoutInput, LayoutResult


class SnapshotEngine(Protocol):
    def compute(self, request: LayoutInput) -> LayoutResult: ...


@dataclass(frozen=True, slots=True)
class IncrementalReceipt:
    result: LayoutResult
    reused: bool
    reason: str


class IncrementalLayoutCoordinator:
    """Single-owner one-entry cache with full-compute fallback.

    Invalidate on lifecycle teardown and on external/native resource changes,
    even if the serialized style and measurement tuples appear unchanged.
    The renderer remains responsible for native readback and commit fencing.
    """

    def __init__(self, engine: SnapshotEngine) -> None:
        self._engine = engine
        self._input: LayoutInput | None = None
        self._result: LayoutResult | None = None

    def invalidate(self) -> None:
        self._input = None
        self._result = None

    def compute(
        self,
        request: LayoutInput,
        *,
        semantic_invalidation: bool = False,
    ) -> IncrementalReceipt:
        previous = self._input
        prior_result = self._result
        if (not semantic_invalidation and previous is not None
                and prior_result is not None
                and previous.schema_version == request.schema_version
                and previous.direction == request.direction
                and previous.constraints == request.constraints
                and previous.nodes == request.nodes
                and previous.measurements == request.measurements):
            if (prior_result.schema_version == request.schema_version
                    and {name for name, _ in prior_result.boxes}
                    == {node.node_id for node in request.nodes}):
                return IncrementalReceipt(
                    replace(prior_result, generation=request.generation),
                    True,
                    "identical-layout-input",
                )
        # Only publish successfully completed computations. A thrown exception
        # must never make a new snapshot eligible for reuse.
        self.invalidate()
        computed = self._engine.compute(request)
        if (computed.generation != request.generation
                or computed.schema_version != request.schema_version
                or {name for name, _ in computed.boxes}
                != {node.node_id for node in request.nodes}):
            raise ValueError("Cinnamon returned an incompatible layout result.")
        self._input = request
        self._result = computed
        return IncrementalReceipt(computed, False, "full-compute")
