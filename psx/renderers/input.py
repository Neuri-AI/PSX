"""Direct application of the closed portable Input contract."""
from __future__ import annotations

import importlib
from collections.abc import Mapping

from psx.core.errors import RendererCapabilityError
from psx.core.vnode import INPUT_DEFAULTS, INPUT_PROPS, validate_input_props


def input_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_input_props(props)
    return {**INPUT_DEFAULTS, **props}


def updated_input_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - INPUT_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Input props: {', '.join(sorted(unknown))}")
    props = {name: value for name, value in current.items() if name not in removed}
    props.update(changed)
    return input_props(props)


def apply_qt_input(widget: object, props: Mapping[str, object], binding: str) -> None:
    p = input_props(props)
    gui = importlib.import_module(f"{binding}.QtGui")
    widgets = importlib.import_module(f"{binding}.QtWidgets")

    font = gui.QFont()
    font.setPixelSize(max(1, round(p["font_size"])))
    widget.setFont(font)

    widget.setPlaceholderText(str(p["placeholder"]))
    widget.setReadOnly(bool(p["read_only"]))
    widget.setEnabled(bool(p["enabled"]))

    echo_mode = (
        widgets.QLineEdit.EchoMode.Password
        if p["password"]
        else widgets.QLineEdit.EchoMode.Normal
    )
    widget.setEchoMode(echo_mode)

    new_val = str(p["value"])
    if widget.text() != new_val:
        cursor_pos = widget.cursorPosition()
        was_blocked = widget.signalsBlocked()
        widget.blockSignals(True)
        try:
            widget.setText(new_val)
        finally:
            widget.blockSignals(was_blocked)
        widget.setCursorPosition(min(cursor_pos, len(new_val)))


def apply_tk_input(widget: object, props: Mapping[str, object], var: object) -> None:
    from tkinter.font import nametofont

    p = input_props(props)
    family = nametofont("TkDefaultFont", root=widget).actual("family")
    font = (family, -max(1, round(p["font_size"])))
    widget.configure(font=font)

    if not p["enabled"]:
        widget.state(("disabled",))
    elif p["read_only"]:
        widget.state(("readonly",))
    else:
        widget.state(("!disabled", "!readonly"))

    placeholder_text = str(p["placeholder"])
    widget._psx_placeholder = placeholder_text
    widget._psx_password = p["password"]

    is_placeholder_active = getattr(widget, "_psx_placeholder_active", False)
    if p["password"] and not is_placeholder_active:
        widget.configure(show="*")
    elif not p["password"]:
        widget.configure(show="")

    new_val = str(p["value"])
    current_val = "" if is_placeholder_active else var.get()

    if current_val != new_val:
        try:
            cursor_pos = widget.index("insert")
        except Exception:
            cursor_pos = len(new_val)

        widget._psx_updating = True
        try:
            if new_val == "" and placeholder_text and not (widget.focus_get() == widget):
                var.set(placeholder_text)
                widget.configure(foreground="gray", show="")
                widget._psx_placeholder_active = True
            else:
                var.set(new_val)
                widget.configure(foreground="")
                if p["password"]:
                    widget.configure(show="*")
                widget._psx_placeholder_active = False
        finally:
            widget._psx_updating = False

        try:
            widget.icursor(min(cursor_pos, len(new_val)))
        except Exception:
            pass


def apply_kivy_input(widget: object, props: Mapping[str, object]) -> None:
    p = input_props(props)
    widget.font_size = p["font_size"]
    widget.hint_text = str(p["placeholder"])
    widget.disabled = not p["enabled"]
    widget.readonly = bool(p["read_only"])
    widget.password = bool(p["password"])

    new_val = str(p["value"])
    if widget.text != new_val:
        cursor = widget.cursor
        widget._psx_updating = True
        try:
            widget.text = new_val
        finally:
            widget._psx_updating = False
        try:
            widget.cursor = cursor
        except Exception:
            pass