"""Qt Link handlers must not shadow restored href navigation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psx.core.vnode import Flex, Link
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
        reconciler.render(Flex(Link("Submit", on_click=lambda: clicked.append(True))))
        widget = reconciler.root.children[0].handle.widget
        widget.click()
        assert clicked == [True] and not visited
        reconciler.render(Flex(Link("Submit", href="https://google.com")))
        assert reconciler.root.children[0].handle.widget is widget
        widget.click()
        assert clicked == [True]
        assert visited == ["https://google.com"]
    finally:
        reconciler.unmount()
