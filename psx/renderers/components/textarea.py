from collections.abc import Mapping

from psx.core.contracts import TEXTAREA_DEFAULTS, TEXTAREA_PROPS, validate_textarea_props
from psx.core.errors import RendererCapabilityError


def textarea_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_textarea_props(props)
    return {**TEXTAREA_DEFAULTS, **props}


def updated_textarea_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - TEXTAREA_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported TextArea props: {', '.join(sorted(unknown))}"
        )
    result = {k: v for k, v in current.items() if k not in removed}
    result.update(changed)
    return textarea_props(result)

def apply_qt_textarea(widget, props, binding):
    # Texto — bloquear señales para no disparar on_change programáticamente
    if widget.toPlainText() != props["value"]:
        widget.blockSignals(True)
        widget.setPlainText(props["value"])
        widget.blockSignals(False)

    # Placeholder
    widget.setPlaceholderText(props["placeholder"])

    # Tamaño de fuente
    font = widget.font()
    font.setPointSize(int(round(props["font_size"])))
    widget.setFont(font)

    # Read-only / enabled
    widget.setReadOnly(props["read_only"])
    widget.setEnabled(props["enabled"])

def apply_kivy_textarea(widget, props):
    widget._psx_updating = True

    if widget.text != props["value"]:
        widget.text = props["value"]

    widget.hint_text = props["placeholder"]
    widget.font_size = props["font_size"]
    widget.readonly = props["read_only"]
    widget.disabled = not props["enabled"]
    # multiline=True es el valor por defecto en Kivy TextInput

    widget._psx_updating = False

def apply_tk_textarea(widget, props):
    widget._psx_updating = True

    # Establecer contenido (Tkinter Text no tiene set directo)
    current = widget.get("1.0", "end-1c")
    if current != props["value"]:
        widget.delete("1.0", "end")
        widget.insert("1.0", props["value"])

    widget.configure(
        font=("TkDefaultFont", int(round(props["font_size"]))),
        state=(
            "disabled" if not props["enabled"] else
            "normal"
        ),
    )
    # read_only no es un estado nativo de tk.Text; se simula bloqueando edición
    # mediante bind de teclas, o se ignora en esta implementación base.

    widget._psx_updating = False