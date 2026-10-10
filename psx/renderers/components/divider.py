"""Portable Divider prop normalization shared by native renderers."""

from collections.abc import Mapping

from psx.core.contracts import DIVIDER_DEFAULTS, DIVIDER_PROPS, validate_divider_props
from psx.core.errors import RendererCapabilityError


def divider_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_divider_props(props)
    return {**DIVIDER_DEFAULTS, **props}


def updated_divider_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - DIVIDER_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Divider props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return divider_props(result)


def needs_custom_paint(props: Mapping[str, object]) -> bool:
    """True cuando el separador nativo no basta y hay que pintarlo a mano."""
    return props["color"] is not None or props["thickness"] != 1