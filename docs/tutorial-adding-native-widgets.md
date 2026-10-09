# Tutorial: adding a native widget

Use `NativeWidget` when a control has backend-specific behavior. `WebView` is the executable example in `psx.extensions.qt_webengine`; it exposes PySide6 `QWebEngineView` without changing PSX markup, reconciliation, or scheduling.

## 1. Keep the optional import lazy

Import the toolkit inside a helper, not at PSX module import time:

```python
def load_types():
    from PySide6.QtWebEngineWidgets import QWebEngineView
    return QWebEngineView
```

This lets applications without WebEngine import `psx` normally.

## 2. Declare ownership, updates, and events

An owned factory is destroyed by PSX. A supplied instance must use borrowed ownership and is never destroyed by PSX. WebView maps `url`/`html` updates and Qt signals explicitly.

```python
from psx.core.native import NativeWidget

declaration = NativeWidget(
    renderer="pyside6",
    factory=load_types(),
    update=update_webview,
    bind_event=bind_webview_event,
    name="QWebEngineView",
)
```

`update_webview(widget, changed, removed)` must define removal behavior. `bind_webview_event(widget, event, slot)` must connect one callback and return a disposer that disconnects that exact callback.

## 3. Create an ergonomic external component

`WebView` turns friendly props into Native signal names and returns `native_widget(declaration, ...)`. It supports `url`, `html`, `on_load_finished`, `on_url_changed`, `key`, and `ref`.

```python
from psx import Column, builtin_component_registry, psx
from psx.extensions import WebView

registry = builtin_component_registry()
registry.register("WebView", WebView)
node = psx(
    '<Column><WebView url={url} on_load_finished={ready} /></Column>',
    scope={"url": "https://example.test", "ready": print}, registry=registry,
)
```

The registry makes the tag available only where requested. Existing markup and the default registry remain unchanged.

## 4. Validate identity and cleanup

Render a compatible `WebView` twice with the same key, assert the `QWebEngineView` instance is unchanged, emit a signal before and after replacing the callback, then unmount and assert the ref is cleared. This is implemented in `tests/test_qt_webengine_extension.py`.

## Backend notes

- PySide6 WebEngine requires `PySide6.QtWebEngineWidgets`; use an offscreen Qt platform and Chromium no-sandbox flags in CI.
- PyQt5/PyQt6 use the same `NativeWidget` model but must import their own binding only in their extension package.
- Kivy media/native controls need provider-specific lifecycle code; keep it in an optional extension.
- Tkinter widgets normally need a factory accepting the PSX parent (`takes_parent=True`).
- Headless adapters are useful for deterministic lifecycle tests even when no real widget exists.

## Troubleshooting

- A renderer mismatch means the declaration's `renderer` does not match the selected backend.
- “No event adapter” means `bind_event` was omitted or did not handle the declared signal.
- Do not pass changing native callbacks directly through a new connection; return a disposer and let `EventSlot` update the callback.
- Never claim a native prop is portable unless every supported backend has an explicit contract and tests.
