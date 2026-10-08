# M10 — Native interoperability

M10 provides a deliberate escape hatch for native controls that PSX does not
model yet. It is not a portability layer: a declaration names the renderer it
requires, so unsupported bindings fail with `RendererCapabilityError` instead
of attempting an unsafe conversion.

Native adapters are available for every graphical renderer:

- `pyside6`, `pyqt6`, and `pyqt5` accept their matching `QWidget` instances,
  including `QWebEngineView`, `QOpenGLWidget`, and third-party Qt widgets.
- `tkinter` accepts `tkinter.Misc` widgets, including `ttk` and custom Tk
  controls.
- `kivy` accepts `kivy.uix.widget.Widget` subclasses.

Each declaration is bound to exactly one renderer. A `pyside6` control is not
silently accepted by PyQt, and a Kivy widget is not treated as a Tk widget.

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from psx import Column, Native


def render():
    return Column(
        Native(
            QWebEngineView,
            props={"url": "https://example.com"},
            signals={"loadFinished": lambda ok: print(ok)},
            key="browser",
        )
    )
```

`Native(...)` infers the backend from its widget class, creates an owned native
control, and preserves the same instance while its class and key remain
compatible. Qt properties use setters (so `url` becomes `setUrl(QUrl(...))`),
Tk properties use `configure`, and Kivy properties use their declared native
properties. Signals are connected once and PSX replaces their callback without
creating duplicate connections.

The equivalent markup keeps M4B's safe reference rules: mappings remain Python
values rather than arbitrary expressions evaluated by the markup runtime.

```python
browser_signals = {"loadFinished": handle_loaded}
return psx("""
    <Column spacing={12}>
        <Native widget={QWebEngineView}
                url={url}
                signals={browser_signals}
                key="browser" />
    </Column>
""")
```

`use_ref()` on a `Native` node exposes the native widget itself, rather than
PSX's internal renderer handle.

Factories are zero-argument by default. For toolkits where the widget must be
constructed with its PSX container as parent—particularly Tk—set
`takes_parent=True`; the factory then receives that native parent.

```python
from tkinter import ttk
from psx import NativeWidget

entry = NativeWidget(
    renderer="tkinter",
    factory=lambda parent: ttk.Entry(parent),
    takes_parent=True,
    name="SearchEntry",
)
```

`NativeWidget` and `native_widget(...)` remain the low-level API for a
specialized, reusable adapter. Supply custom `update` and `bind_event`
functions there when a third-party control needs behavior beyond the standard
property/signal convention.

Ownership is explicit:

- `factory=...` creates an **owned** widget. PSX detaches and schedules its Qt
  deletion during unmount.
- `widget=existing_widget, ownership="borrowed"` mounts a **borrowed** widget.
  PSX never deletes it. Qt and Kivy restore its original parent when removed;
  Tk removes its PSX pack geometry but cannot re-parent widgets (a Tk runtime
  restriction). This is appropriate for widgets owned by Qyro or another
  host; the host remains responsible for its lifetime.

Native nodes cannot have PSX children. Place them inside `Column`, `Row`, or a
native widget whose own adapter manages its content. Events remain native by
default. To expose one declaratively, provide `bind_event(widget, event, slot)`
on the declaration; it must connect the native signal and return a callable
disposer. PSX keeps that connection stable as the Python callback changes and
calls the disposer exactly once on unmount. Alternatively expose a
purpose-built PSX primitive when a portable contract exists.

The adapter validates the native base class for its selected binding. The
headless renderer intentionally accepts no native declarations.
