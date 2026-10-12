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

def apply_tk_input(widget, props, binding=None):
    """Update the real ttk.Entry value, with a non-value hint overlay.

    The hint is a child of the Entry, never inserted into StringVar and
    therefore never sent through on_change or password-mode state.
    """
    import tkinter as tk

    widget._psx_updating = True
    try:
        if widget.var.get() != props["value"]:
            widget.var.set(props["value"])
        widget._psx_placeholder = props["placeholder"]
        size = int(round(props["font_size"]))
        font = ("TkDefaultFont", size)
        widget.configure(
            font=font,
            show="*" if props["password"] else "",
            state=(
                "disabled" if not props["enabled"] else
                "readonly" if props["read_only"] else "normal"
            ),
        )
        if not hasattr(widget, "_psx_hint_label"):
            hint = tk.Label(widget, borderwidth=0, padx=0, pady=0,
                            anchor="w", takefocus=0)
            widget._psx_hint_label = hint
            def sync_hint(*_args):
                if not widget.winfo_exists():
                    return
                show = (
                    bool(getattr(widget, "_psx_placeholder", ""))
                    and not widget.var.get()
                    and widget.focus_get() is not widget
                    and str(widget.cget("state")) != "disabled"
                )
                if show:
                    hint.configure(text=widget._psx_placeholder)
                    hint.place(x=4, rely=0.5, anchor="w")
                else:
                    hint.place_forget()
            widget._psx_sync_hint = sync_hint
            widget.var.trace_add("write", sync_hint)
            widget.bind("<FocusIn>", sync_hint, add="+")
            widget.bind("<FocusOut>", sync_hint, add="+")
            hint.bind("<Button-1>", lambda _event: widget.focus_set())
        hint = widget._psx_hint_label
        hint.configure(font=font, fg="#777777",
                       bg=widget.winfo_toplevel().cget("background"))
        widget._psx_sync_hint()
    finally:
        widget._psx_updating = False
