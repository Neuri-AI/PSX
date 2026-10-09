"""Backend-independent Checkbox property normalization."""
from __future__ import annotations
from collections.abc import Mapping
from psx.core.contracts import CHECKBOX_DEFAULTS, CHECKBOX_PROPS, validate_checkbox_props
from psx.core.errors import RendererCapabilityError

def checkbox_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_checkbox_props(props)
    return {**CHECKBOX_DEFAULTS, **props}

def updated_checkbox_props(current: Mapping[str, object], changed: Mapping[str, object], removed: frozenset[str]) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - CHECKBOX_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Checkbox props: {', '.join(sorted(unknown))}")
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return checkbox_props(result)

def apply_qt_checkbox(widget: object, props: Mapping[str, object]) -> None:
    values = checkbox_props(props)
    widget.setEnabled(bool(values["enabled"]))
    checked = bool(values["checked"])
    if widget.isChecked() != checked:
        blocked = widget.signalsBlocked()
        widget.blockSignals(True)
        try: widget.setChecked(checked)
        finally: widget.blockSignals(blocked)

def apply_kivy_checkbox(widget: object, props: Mapping[str, object]) -> None:
    values = checkbox_props(props)
    widget.disabled = not bool(values["enabled"])
    if widget.active != bool(values["checked"]):
        widget._psx_updating = True
        try: widget.active = bool(values["checked"])
        finally: widget._psx_updating = False

def apply_tk_checkbox(widget: object, props: Mapping[str, object], variable: object) -> None:
    values = checkbox_props(props)
    widget.state(("!disabled",) if values["enabled"] else ("disabled",))
    variable.set(bool(values["checked"]))
