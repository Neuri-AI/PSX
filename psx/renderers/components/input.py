from collections.abc import Mapping

from psx.core.contracts import INPUT_DEFAULTS, INPUT_PROPS, validate_input_props
from psx.core.errors import RendererCapabilityError


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
        raise RendererCapabilityError(
            f"Unsupported Input props: {', '.join(sorted(unknown))}"
        )
    result = {k: v for k, v in current.items() if k not in removed}
    result.update(changed)
    return input_props(result)

def apply_qt_input(widget, props, binding):
    if widget.text() != props["value"]:
        widget.blockSignals(True)
        widget.setText(props["value"])
        widget.blockSignals(False)

    widget.setPlaceholderText(props["placeholder"])

    font = widget.font()
    font.setPointSize(int(round(props["font_size"])))
    widget.setFont(font)

    widget.setReadOnly(props["read_only"])
    widget.setEnabled(props["enabled"])

    cls = type(widget)
    widget.setEchoMode(
        cls.EchoMode.Password if props["password"] else cls.EchoMode.Normal
    )

def apply_kivy_input(widget, props):
    widget._psx_updating = True

    if widget.text != props["value"]:
        widget.text = props["value"]

    widget.hint_text = props["placeholder"]
    widget.font_size = props["font_size"]
    widget.readonly = props["read_only"]
    widget.disabled = not props["enabled"]
    widget.password = props["password"]
    widget.multiline = False   # por si acaso, aunque ya lo fuerza la fábrica

    widget._psx_updating = False

def apply_tk_input(widget, props, binding):
    widget._psx_updating = True

    if widget.var.get() != props["value"]:
        widget.var.set(props["value"])

    widget.configure(
        placeholder=props["placeholder"],
        font=("TkDefaultFont", int(round(props["font_size"]))),
        show="*" if props["password"] else "",
        state=(
            "disabled" if not props["enabled"] else
            "readonly" if props["read_only"] else
            "normal"
        ),
    )

    widget._psx_updating = False