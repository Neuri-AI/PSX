# REF-M5 native interoperability

PSX retains `Native`, `NativeWidget`, native ownership, refs and renderer-thread scheduling as the common escape hatch. Its built-in PySide6 `WebView` tag uses Qt WebView:

```python
from psx.markup import psx

node = psx('<WebView url={url} on_load_finished={ready} />', scope={"url": "https://example.test", "ready": on_ready})
```

`WebView` creates a PSX-owned Qt WebView `QWebView`, hosted in a QWidget so it participates in PSX Flex layout. It requires PySide6 6.11 or later, supports `url` or `html`, `on_load_finished`, `on_url_changed`, refs, stable native signal callbacks and deterministic cleanup. Compatible reconciliation retains the same host instance. Removing `url` or `html` clears its document deterministically.

The module loads PySide6 Qt WebView only when a view is mounted. Qt WebView uses platform browser APIs where available: WKWebView on macOS, WebView2 or WebEngine on Windows, and WebEngine on Linux. The tag is available from the default PSX registry.

## Validation and limits

The real-widget test mounts the tag from markup, updates its URL while retaining identity, replaces a signal callback through the existing `EventSlot`, verifies the native ref and unmounts it.

PyQt6 is absent in this environment, so its existing optional renderer test remains skipped. No Kivy `Video` adapter was added: it needs media-provider-specific integration and remains a future optional backend extension.
