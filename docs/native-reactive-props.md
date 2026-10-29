# Native widgets: construction, reactive props and adapters

This is the public developer contract for embedding a toolkit widget in PSX
Markup. These examples assume the matching toolkit (PySide6, PyQt, Tkinter
or Kivy) is installed and selected as the active renderer.

## 1. Mount a widget unchanged

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from velto.ui import psx

return psx("""
    <Native widget={QWebEngineView}
            width="100%" height="100vh"
            key="browser" />
""")
```

Without `props`, no reactive handler is necessary. The widget is owned by PSX
when a class is supplied. Passing an existing instance borrows it.

## 2. Own the widget: implement update_props(props, changed)

```python
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

class Browser(QWebEngineView):
    def update_props(self, props, changed):
        if "url" in changed:
            url = props["url"]
            if url and not url.startswith(("https://", "http://")):
                url = "https://" + url
            if url:
                self.setUrl(QUrl(url))
```

```jsx
<Native widget={Browser}
        props={{"url": current_url}}
        width="100%" height="100vh"
        key="browser" />
```

The public `props` mapping is **data**, not automatically inferred setter
names. `changed` is a `frozenset[str]` containing names that have been added
or changed, including every initial property on first mount.
On subsequent updates PSX retains the widget instance. If values are
unchanged, the callback is not invoked.

## 3. Third-party widget: native_adapter

```python
import pyqtgraph as pg
from velto.ui import native_adapter

@native_adapter(pg.PlotWidget)
def update_chart(widget, props, changed):
    if not hasattr(widget, "_curve"):
        widget._curve = widget.plot()
    if "data" in changed:
        widget._curve.setData(props["data"])
```

```jsx
<Native widget={pg.PlotWidget}
        kwargs={{"background": "#151515"}}
        props={{"data": cpu_values}}
        width="100%" height="400px"
        key="chart" />
```

The adapter is registered once for the widget class, with superclass
lookup supported. A widget's own `update_props` takes priority over an adapter.
Adapters receive the native widget instance and the same `props, changed`
contract. Register adapters before mounting widgets; registration is
global within the process.

## 4. Constructors versus dynamic data

Use `args` and `kwargs` for constructor-only configuration.
Use `props` for values that can change without remounting.

```jsx
<Native widget={Chart}
        args={chart_args}
        kwargs={{"title": "CPU Usage"}}
        props={{"data": values}}
        key="chart" />
```

Changing constructor arguments changes the native declaration's identity,
causing a local remount. With unchanged constructor inputs and key, reactive
props update in place. Do not mutate constructor argument objects in place.

Layout attributes `width`, `height`, CSS class and style remain owned by
Cinnamon, not by the reactive prop handler.

## 5. Safety and performance

* Updates are synchronous on the UI renderer's thread, not worker threads.
* Only changed props trigger a handler; arrays are compared by object identity
  to avoid O(N) comparisons on interactive layouts. Supply a fresh array when
  the data changes. In-place mutation of the same object is not tracked.
* Removed reactive props currently raise a clear error. Supply an explicit
  reset value instead (e.g. `None`) if supported by your handler.
* A widget receiving non-empty `props` must provide `update_props` or have
  an `@native_adapter`; there is no automatic setter guessing for the
  `props` mapping.
* For existing users, flat native properties such as
  `<Native widget={QLabel} text="hello" />` retain their legacy
  toolkit-property behavior. Prefer the explicit `props` mapping for new
  reactive integrations.
* Event bindings (`signals`), `ref`, native ownership and geometry remain
  governed by the existing Native contract.
