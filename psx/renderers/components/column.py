from collections.abc import Mapping

from psx.core.contracts import COLUMN_DEFAULTS, COLUMN_PROPS, validate_column_props
from psx.core.errors import RendererCapabilityError


def column_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_column_props(props)
    return {**COLUMN_DEFAULTS, **props}


def updated_column_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - COLUMN_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Column props: {', '.join(sorted(unknown))}"
        )
    result = {k: v for k, v in current.items() if k not in removed}
    result.update(changed)
    return column_props(result)


# Portable helpers (no GUI imports). ``expand`` may be positional: a tuple's
# values follow child order, so callers should use stable keys when reordering.

def normalize_padding(value: object) -> tuple[int, int, int, int]:
    """Devuelve siempre (l, t, r, b)."""
    if isinstance(value, int):
        return (value, value, value, value)
    if len(value) == 2:
        h, v = value
        return (h, v, h, v)
    return tuple(value)  # type: ignore[return-value]


def child_align(props: Mapping[str, object], index: int) -> str:
    align = props.get("align", "stretch")
    if isinstance(align, str):
        return align
    # Reserved for a future per-child alignment API.
    return align[index] if index < len(align) else "stretch"


def child_expand(props: Mapping[str, object], index: int) -> bool:
    expand = props.get("expand", False)
    if isinstance(expand, bool):
        return expand
    return expand[index] if index < len(expand) else False
