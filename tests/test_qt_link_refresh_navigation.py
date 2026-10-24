"""Qt Link handlers must not shadow restored href navigation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psx.core.vnode import Link
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


def test_removed_click_handler_restores_href(monkeypatch):
    visited = []
    monkeypatch.setattr("psx.renderers.components.link.webbrowser.open",
                        lambda href: visited.append(href))
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(), argv=["psx-link-refresh"],
    )
    reconciler = Reconciler(renderer)
    clicked = []
    try:
        reconciler.render(Link("Submit", on_click=lambda: clicked.append(True)))
        widget = reconciler.root.handle.widget
        widget.click()
        assert clicked == [True] and not visited
        reconciler.render(Link("Submit", href="https://google.com"))
        assert reconciler.root.handle.widget is widget
        widget.click()
        assert clicked == [True]
        assert visited == ["https://google.com"]
    finally:
        reconciler.unmount()
