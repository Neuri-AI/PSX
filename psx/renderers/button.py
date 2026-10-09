"""Direct application of the closed portable Button contract."""
from __future__ import annotations

import importlib
from collections.abc import Mapping

from psx.core.errors import RendererCapabilityError
from psx.core.vnode import BUTTON_DEFAULTS, BUTTON_PROPS, validate_button_props


def button_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_button_props(props)
    return {**BUTTON_DEFAULTS, **props}


def updated_button_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - BUTTON_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Button props: {', '.join(sorted(unknown))}")
    props = {name: value for name, value in current.items() if name not in removed}
    props.update(changed)
    return button_props(props)


def apply_qt_button(widget: object, props: Mapping[str, object], binding: str) -> None:
    p = button_props(props)
    gui = importlib.import_module(f"{binding}.QtGui")
    font = gui.QFont()
    font.setPixelSize(max(1, round(p["font_size"])))
    widget.setFont(font)
    widget.setText(str(p["label"]))
    widget.setEnabled(p["enabled"])


def apply_tk_button(widget: object, props: Mapping[str, object]) -> None:
    from tkinter import ttk
    from tkinter.font import nametofont

    p = button_props(props)
    family = nametofont("TkDefaultFont", root=widget).actual("family")
    style_name = f"PSX.{max(1, round(p['font_size']))}.TButton"
    ttk.Style(widget).configure(style_name, font=(family, -max(1, round(p["font_size"]))))
    widget.configure(text=str(p["label"]), style=style_name)
    widget.state(("!disabled",) if p["enabled"] else ("disabled",))


def apply_kivy_button(widget: object, props: Mapping[str, object]) -> None:
    p = button_props(props)
    widget.text = str(p["label"])
    widget.font_size = p["font_size"]
    widget.disabled = not p["enabled"]
