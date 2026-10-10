"""Backend-neutral numeric normalization and controlled SpinBox semantics."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from psx.core.contracts import SPINBOX_DEFAULTS, SPINBOX_PROPS, validate_spinbox_props
from psx.core.errors import RendererCapabilityError


def spinbox_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_spinbox_props(props)
    return {**SPINBOX_DEFAULTS, **props}


def updated_spinbox_props(
    current: Mapping[str, object], changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - SPINBOX_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported SpinBox props: {', '.join(sorted(unknown))}"
        )
    merged = {key: val for key, val in current.items() if key not in removed}
    merged.update(changed)
    return spinbox_props(merged)


def _decimal(value: int | float | str) -> Decimal:
    return Decimal(str(value))


def normalized(value: Decimal | int | float, props: Mapping[str, object]) -> int | float:
    """Round to selected precision, then clamp within the portable range."""
    digits = int(props["decimals"])
    quantum = Decimal(1).scaleb(-digits)
    lower = _decimal(props["min"])
    upper = _decimal(props["max"])
    result = min(upper, max(lower, _decimal(value)))
    result = result.quantize(quantum, rounding=ROUND_HALF_UP)
    # The validator requires both bounds to be representable at this precision.
    result = min(upper, max(lower, result))
    return int(result) if digits == 0 else float(result)


def formatted(value: int | float, props: Mapping[str, object]) -> str:
    return f"{value:.{int(props['decimals'])}f}"


def parsed(text: str, props: Mapping[str, object]) -> int | float | None:
    """Return None for an invalid/intermediate edit; otherwise normalize."""
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    return normalized(value, props)


def stepped(value: int | float, direction: int, props: Mapping[str, object]) -> int | float:
    candidate = _decimal(value) + _decimal(props["step"]) * direction
    return normalized(candidate, props)


def committed(text: str, props: Mapping[str, object]) -> int | float:
    """Return the normalized edit, or restore the controlled value on invalid text."""
    value = parsed(text, props)
    return normalized(props["value"], props) if value is None else value
