"""REF-M5 real native-widget interoperability coverage."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QCoreApplication, QEvent

from psx import Column, Ref, psx
from psx.core.reconcile import Reconciler
from psx.core.registry import builtin_component_registry
from psx.extensions.qt_webengine import WebView
from psx.renderers.qt.pyside6 import PySide6Renderer


def test_webview_custom_markup_preserves_identity_events_refs_and_cleanup() -> None:
    renderer = PySide6Renderer([])
    reconciler = Reconciler(renderer)
    registry = builtin_component_registry()
    registry.register("WebView", WebView)
    ref: Ref[object] = Ref()
    callbacks: list[tuple[str, bool]] = []
    scope = {"url": "about:blank", "ref": ref, "loaded": lambda ok: callbacks.append(("old", ok))}
    node = psx('<Column><WebView key="engine" url={url} ref={ref} on_load_finished={loaded} /></Column>', scope=scope, registry=registry)
    first = reconciler.render(node).children[0]
    widget = ref.current
    assert isinstance(widget, QWebEngineView)
    assert widget.url().toString() == "about:blank"
    widget.loadFinished.emit(True)
    assert callbacks == [("old", True)]

    scope["url"] = "https://example.test/next"
    scope["loaded"] = lambda ok: callbacks.append(("new", ok))
    second = reconciler.render(psx('<Column><WebView key="engine" url={url} ref={ref} on_load_finished={loaded} /></Column>', scope=scope, registry=registry)).children[0]
    assert second.handle is first.handle
    assert ref.current is widget
    assert widget.url().toString() == "https://example.test/next"
    widget.loadFinished.emit(True)
    assert callbacks == [("old", True), ("new", True)]

    reconciler.unmount()
    assert ref.current is None
    # Deliver Qt's deferred native destruction before pytest tears down the
    # process; WebEngine owns a helper process while a view is alive.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    renderer.application.processEvents()
