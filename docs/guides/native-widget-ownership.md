# Native widget ownership and borrowing

PSX supports embedding toolkit-native widgets through `Native`, but
**creating a widget for PSX** and **lending PSX an existing widget instance**
have different lifetime guarantees.

## Ownership model

| Toolkit | PSX-owned widget (factory/class) | Existing borrowed widget |
| --- | --- | --- |
| Qt (PySide6, PySide2, PyQt6, PyQt5) | Supported: PSX creates and releases it | Supported: PSX temporarily reparents it and restores its previous parent without deleting it |
| Kivy | Supported: PSX creates and detaches it | Supported: PSX transfers it temporarily, then restores the caller parent and original layout hints |
| Tkinter | Supported: PSX creates it with the correct master and destroys it on unmount | **Unsupported**: fail closed before mutating the supplied instance |

**Why Tkinter is different:** Tkinter fixes a widget's `master` when it
is constructed. Unlike Qt's `setParent()` or Kivy's
`remove_widget()`/`add_widget()`, Tkinter provides no supported
operation for changing an existing widget's master. Furthermore,
destroying a Tkinter container destroys its children. If PSX accepted
a caller-owned widget inside a PSX-owned container, PSX could not
guarantee that unmount would preserve the caller's instance.

**Policy:** Borrowing means that PSX may temporarily mount an existing
native object but **must not destroy it**. Since Tkinter cannot meet that
contract, `Native(existing_tk_widget)` in the SFLE-backed adapter raises
`RendererCapabilityError` before placement, property updates or event
binding. This is an explicit capability restriction, not a limitation
of SFLE's geometry algorithm.

## Supported: let PSX create a Tkinter widget

```python
import tkinter as tk

from psx import Flex
from psx.core.native import Native

# Construct a declaration from a class/factory, not an existing instance.
# The renderer creates the actual button under the correct Tk master.
view = Flex(
    Native(
        tk.Button,
        renderer="tkinter",
        # An explicit SFLEExternalPort is required for an external
        # leaf in SFLE mode; configure measure/apply/read for this widget.
        sfle_port=button_port,
        text="Run",
        layout_width="100px",
        layout_height="30px",
    ),
    width=240,
    height=80,
)
```

`button_port` represents a developer-supplied
`SFLEExternalPort(measure, apply, read)`. It is not a built-in implicit
adapter or an automatic fallback to `pack`, `grid` or `place`.

## Unsupported: lend an existing Tkinter widget

```python
import tkinter as tk

from psx.core.native import Native

root = tk.Tk()
original_panel = tk.Frame(root)
button = tk.Button(original_panel, text="Caller-owned")

# Rejected in the SFLE-enabled Tk renderer:
declaration = Native(button, renderer="tkinter", sfle_port=button_port)
```

Creating the `Native` declaration does not itself mount the widget:
the renderer rejects it when PSX attempts to create/mount the
native node. The existing `button` remains the caller's property.
Do **not** depend on PSX relocating the widget, preserving its
lifetime through a foreign master, or restoring its `master`.

## Supported borrowing in Qt and Kivy

With a valid backend-specific `SFLEExternalPort`, a compatible
existing Qt or Kivy widget can be declared as borrowed. PSX retains
the same native object through keyed reconciliation and returns it
to its original parent on unmount. The caller remains responsible
for its final lifetime. In Kivy, PSX also restores the original
`size_hint` and `pos_hint`; these may be temporarily overridden
while SFLE owns geometry. PSX-owned signal subscriptions are detached
on unmount so disposed callbacks cannot be invoked.

The `NativeWidget` declaration enforces either a factory with
`ownership="owned"` **or** an existing instance with
`ownership="borrowed"`, never both. Supplying the wrong renderer,
an invalid ownership pairing or a missing geometry port is an
explicit error.

## Alternatives for Tkinter integration

If you have a reusable widget *class or factory*, have PSX
instantiate it using the correct `master`. If you need a custom
widget, register a toolkit-specific adapter and supply explicit
SFLE measurement, application, readback and resource-disposal
callbacks. An adapter does not make an existing Tk widget reparentable:
it must respect Tk's master and destruction rules.

If an external Tk widget must remain managed by legacy code, leave it
under its caller-owned `master` and integrate at an appropriate
application boundary instead of presenting it as a borrowed PSX child.

**Scope:** This guide describes the C4 ownership contract. It is not
a claim of complete method/property/event parity across toolkits.
The final functional audit belongs to F3-G5.
