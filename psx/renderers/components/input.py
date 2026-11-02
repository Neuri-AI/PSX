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
    font.setPixelSize(max(1, round(props["font_size"])))
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

def apply_tk_input(widget, props, binding=None):
    """Render a Tk Entry placeholder in its text plane without an opaque label.

    A separate display StringVar holds hints; widget.var remains the real
    application value and never contains the placeholder.
    """
    widget._psx_updating = True
    try:
        if widget.var.get() != props["value"]:
            widget.var.set(props["value"])
        widget._psx_placeholder = props["placeholder"]
        widget._psx_password = bool(props["password"])
        size = max(1, round(props["font_size"]))
        widget.configure(
            font=("TkDefaultFont", -size),
            state=(
                "disabled" if not props["enabled"] else
                "readonly" if props["read_only"] else "normal"
            ),
        )
        if not hasattr(widget, "_psx_sync_hint"):
            widget._psx_input_foreground = str(widget.cget("foreground"))
            widget._psx_hint_active = False

            def sync_hint(*_args):
                if not widget.winfo_exists():
                    return
                actual = widget.var.get()
                show_hint = (
                    bool(widget._psx_placeholder)
                    and not actual
                    and widget.focus_get() is not widget
                    and str(widget.cget("state")) != "disabled"
                )
                display = widget._psx_placeholder if show_hint else actual
                widget._psx_hint_active = show_hint
                if widget._psx_display_var.get() != display:
                    previous = widget._psx_updating
                    widget._psx_updating = True
                    try:
                        widget._psx_display_var.set(display)
                    finally:
                        widget._psx_updating = previous
                widget.configure(
                    show="" if show_hint or not widget._psx_password else "*",
                    foreground=(
                        "#777777" if show_hint
                        else widget._psx_input_foreground
                    ),
                )

            def sync_edit(*_args):
                if (getattr(widget, "_psx_updating", False)
                        or widget._psx_hint_active):
                    return
                entered = widget._psx_display_var.get()
                if widget.var.get() != entered:
                    widget.var.set(entered)

            widget._psx_sync_hint = sync_hint
            widget._psx_display_var.trace_add("write", sync_edit)
            widget.var.trace_add("write", sync_hint)
            widget.bind("<FocusIn>", sync_hint, add="+")
            widget.bind("<FocusOut>", sync_hint, add="+")
        widget._psx_sync_hint()
    finally:
        widget._psx_updating = False
