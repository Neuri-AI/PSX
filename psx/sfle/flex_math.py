"""Pure CSS Flexbox main-size distribution kernel (F2.2, not a full engine).

Implements the flexible-length freezing loop from CSS Flexbox §9.7 for
already-resolved, content-box main sizes in *one flex line*. This module
does not form lines, resolve percentage/intrinsic bases, account for
padding/border/margins, or position boxes. Callers must not advertise a
complete layout capability merely because this kernel is available.

The companion Rust module follows the same numeric steps and will be
checked against shared fixtures before exposing its capabilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return float(value)


@dataclass(frozen=True, slots=True)
class FlexBasis:
    """Already-resolved main-axis sizes for one item in a single line.

    `basis` is the flex base size. `hypothetical` is the precomputed
    hypothetical main size after min/max clamps. Min/max must be used
    content-box lengths, not unresolved CSS expressions.
    """

    basis: float
    hypothetical: float
    grow: float = 0.0
    shrink: float = 1.0
    min_size: float = 0.0
    max_size: float | None = None

    def __post_init__(self) -> None:
        for name in ("basis", "hypothetical", "grow", "shrink", "min_size"):
            value = _number(getattr(self, name), f"FlexBasis.{name}")
            if value < 0:
                raise ValueError(f"FlexBasis.{name} cannot be negative.")
            object.__setattr__(self, name, value)
        if self.max_size is not None:
            limit = _number(self.max_size, "FlexBasis.max_size")
            if limit < self.min_size:
                raise ValueError("FlexBasis.max_size cannot be below min_size.")
            object.__setattr__(self, "max_size", limit)
        expected = _clamp(self.basis, self.min_size, self.max_size)
        if not math.isclose(self.hypothetical, expected, rel_tol=0, abs_tol=1e-9):
            raise ValueError(
                "FlexBasis.hypothetical must be the min/max-clamped basis. "
                "Resolve CSS intrinsic/auto constraints before invoking this kernel."
            )


def _clamp(value: float, minimum: float, maximum: float | None) -> float:
    return max(minimum, min(value, maximum)) if maximum is not None else max(minimum, value)


def resolve_flexible_lengths(
    items: tuple[FlexBasis, ...],
    container_inner_main_size: float,
    gap: float = 0.0,
) -> tuple[float, ...]:
    """Resolve content-box target main sizes for a single flex line.

    Uses the grow/shrink choice based on the *sum of hypothetical sizes*,
    while shrink distribution weights each item by shrink factor × basis.
    Items are frozen on min/max violations and remaining free space is
    recalculated until the algorithm terminates.

    Preconditions: a definite container main size; no margin, border or
    padding contributions; no percentage or intrinsic resolution; no auto
    margins. `gap` is a resolved, nonnegative per-item gutter.
    """

    if not isinstance(items, tuple) or not all(isinstance(i, FlexBasis) for i in items):
        raise TypeError("items must be a tuple of FlexBasis.")
    available = _number(container_inner_main_size, "container_inner_main_size")
    gutter = _number(gap, "gap")
    if available < 0 or gutter < 0:
        raise ValueError("Container inner size and gap must be nonnegative.")
    if not items:
        return ()

    free_main = available - gutter * (len(items) - 1)
    growing = sum(item.hypothetical for item in items) < free_main
    targets = [item.basis for item in items]
    frozen = [False] * len(items)

    # CSS §9.7: freeze inflexible items, accounting for min/max-constrained
    # hypothetical sizes before distributing any remaining free space.
    for idx, item in enumerate(items):
        factor = item.grow if growing else item.shrink
        if factor == 0 or (
            growing and item.basis > item.hypothetical
        ) or (
            not growing and item.basis < item.hypothetical
        ):
            targets[idx] = item.hypothetical
            frozen[idx] = True

    initial_free = free_main - sum(
        item.hypothetical if is_frozen else item.basis
        for item, is_frozen in zip(items, frozen)
    )

    # At least one previously-unfrozen item is frozen in every non-final
    # iteration; bound the loop to guarantee termination.
    for _ in range(len(items) + 1):
        live = [idx for idx, is_frozen in enumerate(frozen) if not is_frozen]
        if not live:
            return tuple(targets)

        remaining = free_main - sum(
            targets[idx] if frozen[idx] else items[idx].basis
            for idx in range(len(items))
        )
        factors = [items[idx].grow if growing else items[idx].shrink for idx in live]
        total_factor = sum(factors)
        # CSS §9.7 limits free space when total flex factor is below 1.
        if total_factor < 1:
            scaled = initial_free * total_factor
            if abs(scaled) < abs(remaining):
                remaining = scaled

        if growing:
            weights = factors
        else:
            weights = [items[idx].shrink * items[idx].basis for idx in live]
        weight_sum = sum(weights)

        for idx, weight in zip(live, weights):
            contribution = (remaining * weight / weight_sum) if weight_sum > 0 else 0.0
            targets[idx] = items[idx].basis + contribution

        # The Flexbox algorithm clamps target sizes before identifying
        # min/max violations. Compare against the *unclamped* target.
        violations = {}
        total_violation = 0.0
        for idx in live:
            unclamped = targets[idx]
            clamped = _clamp(max(0.0, unclamped), items[idx].min_size, items[idx].max_size)
            targets[idx] = clamped
            violations[idx] = clamped - unclamped
            total_violation += violations[idx]

        if math.isclose(total_violation, 0.0, abs_tol=1e-12):
            return tuple(targets)

        # Positive total violation freezes min-violating items; negative
        # freezes max-violating items, per §9.7.
        to_freeze = [
            idx for idx in live
            if violations[idx] > 0 if total_violation > 0
        ] if total_violation > 0 else [
            idx for idx in live if violations[idx] < 0
        ]
        if not to_freeze:
            raise RuntimeError("Flex size freeze loop made no progress.")
        for idx in to_freeze:
            frozen[idx] = True

    raise RuntimeError("Flex size freeze loop did not converge.")
