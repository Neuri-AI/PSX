"""Native Tk observations and input events for public behavior certification."""
import re
from tkinter import font, ttk
import psx


def control(name, **props):
    props = {"key": "control", "layout_width": "180px", "layout_height": "40px",
             "flex_basis": "180px", "flex_shrink": 0, **props}
    if name == "Text":
        return psx.Text(props.pop("value", "Text"), **props)
    if name == "Button":
        return psx.Button(props.pop("label", "Activate"), **props)
    if name == "Radio":
        return psx.Radio(props.pop("value", "a"), **props)
    return getattr(psx, name)(**props)


def view(name, **props):
    return psx.Flex(control(name, **props), width="400px", height="120px",
                    align_items="flex-start")


def native_font(widget):
    if isinstance(widget, ttk.Button):
        return font.Font(root=widget, font=ttk.Style(widget).lookup(widget.cget("style"), "font"))
    return font.Font(root=widget, font=widget.cget("font"))


def configured_font_size(widget):
    """Read the exact pixel size configured on the actual native widget/style.

    Tk's ``font actual`` converts pixel-sized fonts to DPI-dependent points,
    so it is not a readback of PSX's pixel contract.
    """
    spec = (ttk.Style(widget).lookup(widget.cget("style"), "font")
            if isinstance(widget, ttk.Button) else widget.cget("font"))
    match = re.search(r"(?:^|\s)(-?\d+)(?:\s|$)", str(spec))
    if match is None:
        raise AssertionError(f"Native font has no explicit size: {spec!r}")
    return abs(int(match.group(1)))


def enabled(widget):
    if hasattr(widget, "instate"):
        return not widget.instate(("disabled",))
    return str(widget.cget("state")) != "disabled"


def keyboard(root, widget, sequence):
    widget.focus_force()
    root.update()
    widget.event_generate(sequence)
    root.update()


def click(root, widget):
    root.update()
    x, y = max(1, widget.winfo_width() // 2), max(1, widget.winfo_height() // 2)
    widget.event_generate("<Enter>", x=x, y=y)
    widget.event_generate("<ButtonPress-1>", x=x, y=y)
    widget.event_generate("<ButtonRelease-1>", x=x, y=y)
    root.update()
