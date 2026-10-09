"""Portable Row property handling shared by native renderers."""

from collections.abc import Mapping

from psx.core.contracts import ROW_DEFAULTS, ROW_PROPS, validate_row_props
from psx.core.errors import RendererCapabilityError
from .column import child_align, child_expand, normalize_padding


def updated_row_props(
    current: Mapping[str, object], changed: Mapping[str, object], removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - ROW_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Row props: {', '.join(sorted(unknown))}")
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    validate_row_props(result)
    return {**ROW_DEFAULTS, **result}
