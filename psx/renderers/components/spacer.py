"""Portable Spacer prop normalization shared by native renderers."""

from collections.abc import Mapping

from psx.core.contracts import SPACER_DEFAULTS, SPACER_PROPS, validate_spacer_props
from psx.core.errors import RendererCapabilityError


def spacer_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_spacer_props(props)
    return {**SPACER_DEFAULTS, **props}


def updated_spacer_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - SPACER_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Spacer props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return spacer_props(result)


# Per-backend apply helpers. Each one just tags the widget so the parent
# container adapter knows it must give it the free main-axis space.

def apply_qt_spacer(widget: object, props: Mapping[str, object]) -> None:
    widget._psx_is_spacer = True  # type: ignore[attr-defined]


def apply_kivy_spacer(widget: object, props: Mapping[str, object]) -> None:
    widget._psx_is_spacer = True  # type: ignore[attr-defined]


def apply_tk_spacer(widget: object, props: Mapping[str, object]) -> None:
    widget._psx_is_spacer = True  # type: ignore[attr-defined]