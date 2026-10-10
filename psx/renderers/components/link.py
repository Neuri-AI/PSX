"""Shared portable Link normalization and navigation semantics."""

from __future__ import annotations

import webbrowser
from collections.abc import Mapping

from psx.core.contracts import LINK_DEFAULTS, LINK_PROPS, validate_link_props
from psx.core.errors import RendererCapabilityError


def link_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_link_props(props)
    return {**LINK_DEFAULTS, **props}


def updated_link_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - LINK_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Link props: {', '.join(sorted(unknown))}"
        )
    merged = {k: v for k, v in current.items() if k not in removed}
    merged.update(changed)
    return link_props(merged)


def activate_link(props: Mapping[str, object]) -> None:
    """Navigate to an external URL only; callback links use PSX EventSlot."""
    if props["enabled"] and props["href"] is not None:
        webbrowser.open(props["href"])
