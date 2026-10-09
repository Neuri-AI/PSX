"""Direct application of the closed portable Text contract."""
from __future__ import annotations

import importlib
from collections.abc import Mapping

from psx.core.errors import RendererCapabilityError
from psx.core.contracts import TEXT_DEFAULTS, TEXT_PROPS, validate_text_props


def text_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_text_props(props)
    return {**TEXT_DEFAULTS, **props}


def updated_text_props(current: Mapping[str, object], changed: Mapping[str, object],
                       removed: frozenset[str]) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - TEXT_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Text props: {', '.join(sorted(unknown))}")
    props = {name: value for name, value in current.items() if name not in removed}
    props.update(changed)
    return text_props(props)


def apply_qt_text(widget: object, props: Mapping[str, object], binding: str) -> None:
    p = text_props(props)
    gui = importlib.import_module(f"{binding}.QtGui")
    qt = importlib.import_module(f"{binding}.QtCore").Qt
    enum = getattr(qt, "AlignmentFlag", qt)
    font = gui.QFont()
    font.setPixelSize(max(1, round(p["font_size"])))
    font.setBold(p["bold"])
    font.setItalic(p["italic"])
    widget.setFont(font)
    widget.setStyleSheet("" if p["color"] is None else f"color: {p['color']};")
    widget.setAlignment({"left": enum.AlignLeft, "center": enum.AlignHCenter,
                         "right": enum.AlignRight}[p["align"]] | enum.AlignVCenter)
    widget.setTextFormat(getattr(getattr(qt, "TextFormat", qt), "PlainText"))
    widget.setText(str(p["value"]))
    widget.setEnabled(p["enabled"])


def apply_tk_text(widget: object, props: Mapping[str, object]) -> None:
    from tkinter.font import nametofont
    p = text_props(props)
    family = nametofont("TkDefaultFont", root=widget).actual("family")
    styles = ("bold" if p["bold"] else "normal") + " " + ("italic" if p["italic"] else "roman")
    widget.configure(text=str(p["value"]), font=(family, -max(1, round(p["font_size"])), styles),
                     foreground="" if p["color"] is None else p["color"], justify=p["align"],
                     anchor={"left": "w", "center": "center", "right": "e"}[p["align"]])
    widget.state(("!disabled",) if p["enabled"] else ("disabled",))


def apply_kivy_text(widget: object, props: Mapping[str, object]) -> None:
    p = text_props(props)
    widget.text = str(p["value"])
    widget.font_size = p["font_size"]
    widget.bold = p["bold"]
    widget.italic = p["italic"]
    if p["color"] is None:
        widget.color = widget.property("color").defaultvalue
        widget.disabled_color = widget.property("disabled_color").defaultvalue
    else:
        widget.color = [int(p["color"][i:i+2], 16) / 255 for i in (1, 3, 5)] + [1]
        widget.disabled_color = widget.color
    widget.halign = p["align"]
    widget.valign = "middle"
    widget.disabled = not p["enabled"]


def size_kivy_text(widget: object, size: object) -> None:
    """Keep alignment relative to label bounds when its layout resizes."""
    widget.text_size = size
