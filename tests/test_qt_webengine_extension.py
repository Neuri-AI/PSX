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
    # Setting the URL can itself emit a native navigation notification. Check
    # rebinding independently of notifications produced during that update.
    callbacks.clear()
    widget.web_view.urlChanged.emit(QUrl("https://example.test/second"))
    assert callbacks == ["new:https://example.test/second"]

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


def test_webview_native_src_passes_local_file_url_to_qt(tmp_path, monkeypatch) -> None:
    """Test the adapter contract without requiring an active OS browser view.

    QtWebView hosts a platform-native QWindow; in QT_QPA_PLATFORM=offscreen,
    setUrl() can be called without its url() property reflecting the change.
    Only a graphical-platform test may assert real navigation/loading.
    """
    from psx.extensions import qt_webengine

    class RecordingWebView:
        def __init__(self) -> None:
            self.urls: list[QUrl] = []
            self.html: list[tuple[str, QUrl | None]] = []

        def setUrl(self, url: QUrl) -> None:
            self.urls.append(url)

        def loadHtml(self, html: str, base_url: QUrl | None = None) -> None:
            self.html.append((html, base_url))

    local = tmp_path / "index.html"
    local.write_text("<html><body>Velto</body></html>", encoding="utf-8")
    view = RecordingWebView()
    host = object()
    monkeypatch.setattr(qt_webengine, "_native_view", lambda widget: view)

    qt_webengine._update(host, {"src": str(local)}, frozenset())
    assert view.urls == []
    assert len(view.html) == 1
    document, base_url = view.html[0]
    assert "Velto" in document
    assert base_url is not None and base_url.isLocalFile()
    assert base_url.toLocalFile() == str(local)

    qt_webengine._update(host, {"src": "https://example.test/"}, frozenset())
    assert view.urls[-1].scheme() == "https"
    assert view.urls[-1].toString() == "https://example.test/"

    qt_webengine._update(host, {}, frozenset({"src"}))
    assert view.html[-1] == ("", None)


def test_webview_missing_local_html_is_explicit(tmp_path, monkeypatch) -> None:
    import pytest
    from psx.extensions import qt_webengine

    monkeypatch.setattr(qt_webengine, "_native_view", lambda widget: object())
    missing = tmp_path / "missing.html"
    with pytest.raises(FileNotFoundError):
        qt_webengine._update(object(), {"src": str(missing)}, frozenset())



def test_webview_css_survives_expressive_conditional_src() -> None:
    """The JSX ternary path must treat WebView CSS like ordinary PSX markup."""
    from psx.markup.transform import transform_source
    from psx.css.markup import MarkupStyleSource

    source = '''
from psx import psx

def render(render_html, html, current_url):
    return psx("""
        <Webview
            src={render_html ? html : current_url}
            class="webview"
            style="width: 80vw; height: 50vh"
        />
    """)
'''
    transformed = transform_source(source, filename="<webview-expressive>")
    assert transformed.transformed_calls == 1
    assert "_psx_expr_element" in transformed.source
    namespace: dict[str, object] = {}
    exec(compile(transformed.source, "<webview-expressive>", "exec"), namespace)
    render = namespace["render"]

    for enabled, expected in ((False, "https://example.test"), (True, "/tmp/index.html")):
        node = render(enabled, "/tmp/index.html", "https://example.test")
        assert node.props["src"] == expected
        assert "class" not in node.props
        assert isinstance(node.css_source, MarkupStyleSource)
        assert node.css_source.tag == "webview"
        assert node.css_source.classes == frozenset({"webview"})
        assert {"width", "height"}.issubset(node.css_computed.specified)


def test_both_webview_spellings_accept_css_in_expressive_runtime() -> None:
    from psx.markup.expressive_runtime import element

    for tag in ("WebView", "Webview"):
        node = element(
            tag,
            {"src": "about:blank", "class": "browser", "id": "main-browser"},
            (),
            "<test>", 1, 1,
        )
        assert node.props["src"] == "about:blank"
        assert "class" not in node.props
        assert node.css_source.tag == "webview"
        assert node.css_source.classes == frozenset({"browser"})
        assert node.css_source.node_id == "main-browser"
