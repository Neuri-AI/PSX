"""Grid markup must mount below HTML-like box roots with plain text items."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psx.markup.compile import psx
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import LayoutConstraints, AvailableSize


def test_grid_inside_div_with_text_item_is_native_measurable():
    tree = psx('<div><Grid gap="12"><GridItem span="1">hehe</GridItem></Grid></div>')
    assert tree.type == "div"
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(), argv=["grid-html-parent"],
    )
    reconciler = Reconciler(renderer)
    try:
        reconciler.render(tree)
        item = reconciler.root.children[0].children[0]
        assert item.node.type == "GridItem"
        assert item.children[0].node.type == "Text"
        assert item.children[0].handle.widget is not None
    finally:
        reconciler.unmount()


def test_grid_item_html_flow_child_measures_real_text():
    tree = psx('<div><Grid gap="12"><GridItem span="1">'
               '<div><span>hehe</span></div>'
               '</GridItem></Grid></div>')
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(), argv=["grid-html-flow"],
    )
    reconciler = Reconciler(renderer)
    try:
        reconciler.render(tree)
        flow = reconciler.root.children[0].children[0].children[0]
        assert flow.node.type == "div"
        assert flow.children[0].node.type == "span"
        assert flow.children[0].children[0].handle.widget is not None
    finally:
        reconciler.unmount()
