"""Portable Select normalization and backend application helpers."""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import (
    SELECT_DEFAULTS, SELECT_PROPS, validate_select_props,
)
from psx.core.errors import RendererCapabilityError


def select_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_select_props(props)
    return {**SELECT_DEFAULTS, **props}


def updated_select_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - SELECT_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Select props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return select_props(result)


def select_items(props: Mapping[str, object]) -> tuple[tuple[str, str | int], ...]:
    """Normalize option labels and preserve their original typed values."""
    return tuple(
        (option, option) if isinstance(option, str)
        else (option["label"], option["value"])
        for option in props["options"]
    )


def select_label(props: Mapping[str, object]) -> str:
    """Return the selected label or the placeholder for an unset/stale value."""
    for label, value in select_items(props):
        if type(value) is type(props["value"]) and value == props["value"]:
            return label
    return str(props["placeholder"])


def apply_qt_select(widget: object, props: Mapping[str, object], binding: str) -> None:
    p = select_props(props)
    items = select_items(p)
    was_blocked = widget.blockSignals(True)
    try:
        # The placeholder is shown but cannot be selected from the drop-down.
        widget.clear()
        widget.addItem(str(p["placeholder"]), None)
        widget.model().item(0).setEnabled(False)
        selected_index = 0
        for index, (label, value) in enumerate(items, start=1):
            widget.addItem(label, value)
            if type(value) is type(p["value"]) and value == p["value"]:
                selected_index = index
        widget.setCurrentIndex(selected_index)
        widget.setEnabled(bool(p["enabled"]))
    finally:
        widget.blockSignals(was_blocked)


def apply_kivy_select(widget: object, props: Mapping[str, object]) -> None:
    p = select_props(props)
    widget._psx_updating = True
    try:
        widget._psx_items = select_items(p)
        widget.values = tuple(label for label, _ in widget._psx_items)
        widget.text = select_label(p)
        widget.disabled = not bool(p["enabled"])
    finally:
        widget._psx_updating = False
