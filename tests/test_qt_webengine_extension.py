"""REF-M5 real native-widget interoperability coverage."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtWebView import QWebView

from psx import Ref, psx
from psx.core.reconcile import Reconciler
from psx.core.registry import builtin_component_registry
from psx.renderers.qt.pyside import PySide6Renderer


def test_webview_custom_markup_preserves_identity_events_refs_and_cleanup() -> None:
    renderer = PySide6Renderer([])
    reconciler = Reconciler(renderer)
    registry = builtin_component_registry()
    ref: Ref[object] = Ref()
    callbacks: list[str] = []
    scope = {"url": "about:blank", "ref": ref, "changed": lambda url: callbacks.append(url.toString())}
    node = psx('<WebView key="engine" url={url} width="100%" height="100%" ref={ref} on_url_changed={changed} />', scope=scope, registry=registry)
    assert node.type.sfle_port is not None
    assert node.props["layout_width"] == "100%"
    assert node.props["layout_height"] == "100%"
    first = reconciler.render(node)
    widget = ref.current
    assert isinstance(widget.web_view, QWebView)
    assert widget.web_view.url().toString() == "about:blank"
    widget.web_view.urlChanged.emit(QUrl("https://example.test/first"))
    assert callbacks == ["https://example.test/first"]

    scope["url"] = "https://example.test/next"
    scope["changed"] = lambda url: callbacks.append("new:" + url.toString())
    second = reconciler.render(psx('<WebView key="engine" url={url} ref={ref} on_url_changed={changed} />', scope=scope, registry=registry))
    assert second.handle is first.handle
    assert ref.current is widget
    assert widget.web_view.url().toString() == "https://example.test/next"
    widget.web_view.urlChanged.emit(QUrl("https://example.test/second"))
    assert callbacks == ["https://example.test/first", "new:https://example.test/second"]

    reconciler.unmount()
    assert ref.current is None
    # Deliver Qt's deferred native destruction before pytest tears down.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    renderer.application.processEvents()
