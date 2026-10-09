"""PSX declaration adapter for :class:`PySide6.QtWebEngineWidgets.QWebEngineView`.

The optional binding is imported only when this module is imported.  It uses
the existing ``NativeWidget`` escape hatch, so neither markup compilation nor
the reconciler need toolkit knowledge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psx.core.events import EventSlot
from psx.core.native import NativeWidget
from psx.core.vnode import VNode, native_widget


def _load_types() -> tuple[type[Any], type[Any]]:
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError as error:  # pragma: no cover - depends on optional binding
        raise RuntimeError("WebView requires the optional PySide6 WebEngine binding.") from error
    return QWebEngineView, QUrl


def _update(widget: object, changed: dict[str, object], removed: frozenset[str]) -> None:
    _, QUrl = _load_types()
    if "url" in removed or "html" in removed:
        # Clearing is deterministic and avoids retaining stale document content.
        widget.setHtml("")  # type: ignore[attr-defined]
    if "html" in changed:
        widget.setHtml(str(changed["html"]))  # type: ignore[attr-defined]
    if "url" in changed:
        value = changed["url"]
        widget.setUrl(value if isinstance(value, QUrl) else QUrl(str(value)))  # type: ignore[attr-defined]


def _bind_event(widget: object, event: str, slot: EventSlot) -> Callable[[], None]:
    signals = {
        "on_native_signal:loadFinished": "loadFinished",
        "on_native_signal:urlChanged": "urlChanged",
    }
    try:
        signal = getattr(widget, signals[event])
    except KeyError as error:
        raise ValueError(f"WebView does not support event {event!r}.") from error

    def callback(*args: object) -> object:
        return slot.invoke(*args)

    signal.connect(callback)

    def dispose() -> None:
        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            pass

    return dispose


def _declaration() -> NativeWidget:
    QWebEngineView, _ = _load_types()
    return NativeWidget(
        renderer="pyside6",
        factory=QWebEngineView,
        update=_update,
        bind_event=_bind_event,
        name="QWebEngineView",
    )


def WebView(
    *,
    url: str | object | None = None,
    html: str | None = None,
    on_load_finished: Callable[[bool], object] | None = None,
    on_url_changed: Callable[[object], object] | None = None,
    key: str | int | None = None,
    ref: object | None = None,
) -> VNode:
    """Create a PSX-owned QWebEngineView through the existing Native path.

    This is an additive component intended for a custom ``ComponentRegistry``:
    register ``WebView`` and use ``<WebView ... />`` in existing PSX markup.
    ``url`` and ``html`` are mutually exclusive; callback props retain stable
    native signal connections through the reconciler's ``EventSlot``.
    """
    if url is not None and html is not None:
        raise ValueError("WebView accepts either url or html, not both.")
    props: dict[str, object] = {}
    if url is not None:
        props["url"] = url
    if html is not None:
        props["html"] = html
    if on_load_finished is not None:
        if not callable(on_load_finished):
            raise TypeError("on_load_finished must be callable or None.")
        props["on_native_signal:loadFinished"] = on_load_finished
    if on_url_changed is not None:
        if not callable(on_url_changed):
            raise TypeError("on_url_changed must be callable or None.")
        props["on_native_signal:urlChanged"] = on_url_changed
    return native_widget(_declaration(), key=key, ref=ref, **props)
