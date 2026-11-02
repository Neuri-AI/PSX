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


def test_webview_src_and_alias_share_native_descriptor() -> None:
    from psx.extensions import WebView, Webview

    registry = builtin_component_registry()
    assert registry.contains("WebView")
    assert registry.contains("Webview")
    assert Webview is WebView

    for tag in ("WebView", "Webview"):
        node = psx(f'<{tag} src="https://example.test" width="50%" height="25vh" />', registry=registry)
        assert node.props["src"] == "https://example.test"
        assert node.props["layout_width"] == "50%"
        assert node.props["layout_height"] == "25vh"

    legacy = WebView(url="about:blank")
    assert legacy.props["src"] == "about:blank"
    import pytest
    with pytest.raises(ValueError, match="either src or legacy url"):
        WebView(src="about:blank", url="https://example.test")


def test_webview_css_class_preserves_source_and_responsive_dimensions() -> None:
    from psx.css.markup import MarkupStyleSource
    from psx.css.cascade import ComputedStyle

    # CSS can be applied independently of the browser and native renderer.
    from psx.css.markup import compute_markup_styles
    from psx.css.parser import parse_stylesheet

    for tag in ("WebView", "Webview"):
        node = psx(f'<{tag} class="browser" src="about:blank" />')
        assert isinstance(node.css_source, MarkupStyleSource)
        assert "browser" in node.css_source.classes

        styled = compute_markup_styles(
            node,
            parse_stylesheet(".browser { width: 75vw; height: 60%; }"),
        )
        assert isinstance(styled.css_computed, ComputedStyle)
        assert "width" in styled.css_computed.specified
        assert "height" in styled.css_computed.specified
        assert styled.props["src"] == "about:blank"

    inline = psx(
        '<WebView class="browser" style="width: 400px; height: 50vh" '
        'src="about:blank" />'
    )
    assert inline.css_source is not None
    assert inline.css_computed is not None
    assert {"width", "height"}.issubset(inline.css_computed.specified)



def test_webview_src_resolves_absolute_local_paths_and_preserves_urls(tmp_path) -> None:
    from psx.extensions.qt_webengine import _source_url

    local = tmp_path / "site with spaces" / "index.html"
    local.parent.mkdir()
    local.write_text("<html><body>Local page</body></html>", encoding="utf-8")
    local_url = _source_url(str(local), QUrl)
    assert local_url.isLocalFile()
    assert local_url.toLocalFile() == str(local)

    path_object_url = _source_url(local, QUrl)
    assert path_object_url.toLocalFile() == str(local)

    # Absolute paths may be supplied before the target is created.
    missing_path = tmp_path / "missing.html"
    assert _source_url(str(missing_path), QUrl).toLocalFile() == str(missing_path)

    for source in (
        "https://example.test/path?q=1",
        "http://example.test/",
        "file:///tmp/index.html",
        "about:blank",
        "data:text/html,Hello",
    ):
        assert _source_url(source, QUrl).toString() == QUrl(source).toString()

    existing_url = QUrl("https://example.test/keep")
    assert _source_url(existing_url, QUrl) is existing_url


def test_webview_native_src_loads_local_file(tmp_path) -> None:
    from psx.extensions.qt_webengine import _create_webview, _update

    local = tmp_path / "index.html"
    local.write_text("<html><body>Velto</body></html>", encoding="utf-8")
    renderer = PySide6Renderer([])
    widget = _create_webview()
    try:
        _update(widget, {"src": str(local)}, frozenset())
        assert widget.web_view.url().isLocalFile()
        assert widget.web_view.url().toLocalFile() == str(local)

        _update(widget, {"src": "https://example.test/"}, frozenset())
        assert widget.web_view.url().scheme() == "https"
    finally:
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
