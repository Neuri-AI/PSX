"""PSX adapter for Qt WebView's platform-native ``QWebView``.

Qt WebView delegates to the platform browser APIs where available. Its
``QWebView`` is a QWindow, so this adapter hosts it in a QWidget container for
PSX's QWidget-based Qt renderer and SFLE layout bridge.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any

from psx.core.events import EventSlot
from psx.core.native import NativeWidget, _default_sfle_port
from psx.core.props import FLEX_ITEM_PROPS
from psx.core.vnode import VNode, native_widget


def _load_types() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtWebView import QWebView, QWebViewLoadingInfo
        from PySide6.QtWidgets import QVBoxLayout, QWidget
    except ImportError as error:  # pragma: no cover - depends on optional binding
        raise RuntimeError(
            "WebView requires PySide6 >= 6.11 with the QtWebView module."
        ) from error
    return QWebView, QWebViewLoadingInfo, QUrl, QVBoxLayout, QWidget


def _native_view(widget: object) -> object:
    return widget.web_view  # type: ignore[attr-defined]


def _create_webview() -> object:
    QWebView, _, _, QVBoxLayout, QWidget = _load_types()

    class WebViewHost(QWidget):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__()
            self.web_view = QWebView()
            container = QWidget.createWindowContainer(self.web_view, self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(container)

        # Preserve the previous ergonomic names while exposing Qt WebView's
        # native history methods through the ref host.
        def back(self) -> None:
            self.web_view.goBack()

        def forward(self) -> None:
            self.web_view.goForward()

        def goBack(self) -> None:
            self.web_view.goBack()

        def goForward(self) -> None:
            self.web_view.goForward()

        def reload(self) -> None:
            self.web_view.reload()

        def stop(self) -> None:
            self.web_view.stop()

    return WebViewHost()


def _update(widget: object, changed: dict[str, object], removed: frozenset[str]) -> None:
    _, _, QUrl, _, _ = _load_types()
    view = _native_view(widget)
    if "url" in removed or "html" in removed:
        view.loadHtml("")  # type: ignore[attr-defined]
    if "html" in changed:
        view.loadHtml(str(changed["html"]))  # type: ignore[attr-defined]
    if "url" in changed:
        value = changed["url"]
        view.setUrl(value if isinstance(value, QUrl) else QUrl(str(value)))  # type: ignore[attr-defined]


def _bind_event(widget: object, event: str, slot: EventSlot) -> Callable[[], None]:
    _, QWebViewLoadingInfo, _, _, _ = _load_types()
    view = _native_view(widget)
    if event == "on_native_signal:urlChanged":
        signal = view.urlChanged  # type: ignore[attr-defined]

        def callback(url: object) -> object:
            return slot.invoke(url)

    elif event == "on_native_signal:loadFinished":
        signal = view.loadingChanged  # type: ignore[attr-defined]

        def callback(info: object) -> object | None:
            status = info.status()  # type: ignore[attr-defined]
            if status == QWebViewLoadingInfo.LoadStatus.Succeeded:
                return slot.invoke(True)
            if status in (
                QWebViewLoadingInfo.LoadStatus.Failed,
                QWebViewLoadingInfo.LoadStatus.Stopped,
            ):
                return slot.invoke(False)
            return None

    else:
        raise ValueError(f"WebView does not support event {event!r}.")

    signal.connect(callback)

    def dispose() -> None:
        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            pass

    return dispose


@lru_cache(maxsize=1)
def _declaration() -> NativeWidget:
    return NativeWidget(
        renderer="pyside6",
        factory=_create_webview,
        update=_update,
        bind_event=_bind_event,
        sfle_port=_default_sfle_port("pyside6"),
        name="QtWebView.QWebView",
    )


def WebView(
    *,
    url: str | object | None = None,
    html: str | None = None,
    width: str | int | float | None = None,
    height: str | int | float | None = None,
    layout_width: str | int | float | None = None,
    layout_height: str | int | float | None = None,
    on_load_finished: Callable[[bool], object] | None = None,
    on_url_changed: Callable[[object], object] | None = None,
    key: str | int | None = None,
    ref: object | None = None,
    **layout: object,
) -> VNode:
    """Create a platform-native Qt WebView hosted in a PSX QWidget.

    ``WebView`` is a built-in PSX tag. ``width`` and ``height`` are aliases
    for SFLE layout dimensions. ``url`` and ``html`` are mutually exclusive.
    """
    if url is not None and html is not None:
        raise ValueError("WebView accepts either url or html, not both.")
    if width is not None and layout_width is not None:
        raise ValueError("WebView accepts either width or layout_width, not both.")
    if height is not None and layout_height is not None:
        raise ValueError("WebView accepts either height or layout_height, not both.")
    unsupported = set(layout) - FLEX_ITEM_PROPS
    if unsupported:
        raise TypeError("Unsupported WebView properties: " + ", ".join(sorted(unsupported)))

    props: dict[str, object] = dict(layout)
    if url is not None:
        props["url"] = url
    if html is not None:
        props["html"] = html
    if width is not None:
        props["layout_width"] = width
    if height is not None:
        props["layout_height"] = height
    if layout_width is not None:
        props["layout_width"] = layout_width
    if layout_height is not None:
        props["layout_height"] = layout_height
    if on_load_finished is not None:
        if not callable(on_load_finished):
            raise TypeError("on_load_finished must be callable or None.")
        props["on_native_signal:loadFinished"] = on_load_finished
    if on_url_changed is not None:
        if not callable(on_url_changed):
            raise TypeError("on_url_changed must be callable or None.")
        props["on_native_signal:urlChanged"] = on_url_changed
    return native_widget(_declaration(), key=key, ref=ref, **props)
