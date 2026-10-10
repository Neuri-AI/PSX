"""Portable Radio and RadioGroup prop normalization shared by backends."""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import (
    RADIO_DEFAULTS,
    RADIO_PROPS,
    RADIOGROUP_DEFAULTS,
    RADIOGROUP_PROPS,
    validate_radio_props,
    validate_radiogroup_props,
)
from psx.core.errors import RendererCapabilityError


def radio_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_radio_props(props)
    return {**RADIO_DEFAULTS, **props}


def updated_radio_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - RADIO_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Radio props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return radio_props(result)


def radiogroup_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_radiogroup_props(props)
    return {**RADIOGROUP_DEFAULTS, **props}


def updated_radiogroup_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - RADIOGROUP_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported RadioGroup props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return radiogroup_props(result)