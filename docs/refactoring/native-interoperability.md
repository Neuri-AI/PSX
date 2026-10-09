# REF-M5 native interoperability

REF-M5 retains `Native`, `NativeWidget`, native ownership, refs and renderer-thread scheduling as the common escape hatch. It adds an optional, additive declaration adapter for PySide6 WebEngine:

```python
from psx.core.registry import builtin_component_registry
from psx.extensions import WebView
from psx.markup import psx

registry = builtin_component_registry()
registry.register("WebView", WebView)
node = psx('<WebView url={url} on_load_finished={ready} />', scope={"url": "https://example.test", "ready": on_ready}, registry=registry)
```

`WebView` creates a PSX-owned `QWebEngineView` through a `NativeWidget` declaration. Its specialized declaration adapter supports `url` or `html`, `on_load_finished`, `on_url_changed`, refs, stable native signal callbacks and deterministic cleanup. Compatible reconciliation retains the same view instance. Removing `url` or `html` clears its document deterministically.

The optional module imports PySide6 WebEngine only when `psx.extensions.qt_webengine` is imported. Core imports, the default registry, markup compiler, reconciler and scheduler retain no WebEngine dependency. The tag becomes available only in the registry chosen by the application, so built-in PSX markup remains unchanged.

## Validation and limits

Conda `playground` provides `PySide6.QtWebEngineWidgets`; the real-widget test mounts the tag from markup, updates its URL while retaining identity, replaces a signal callback through the existing `EventSlot`, verifies the native ref and unmounts it. It runs with Qt offscreen and Chromium's no-sandbox/GPU-disabled flags for CI. The host may still print harmless Chromium GPU-context diagnostics in a virtual display.

PyQt6 is absent in this environment, so its existing optional renderer test remains skipped. No Kivy `Video` adapter was added: it needs media-provider-specific integration and remains a future optional backend extension.
