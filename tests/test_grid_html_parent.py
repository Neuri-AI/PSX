"""Grid markup must mount below HTML-like box roots with plain text items."""
import os
import pytest
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


def test_grid_item_nested_block_padding_keeps_text_inside_logo():
    from psx.css.context import scoped_css_resources
    source = (
        '<div class="layout"><Grid gap="0px">'
        '<GridItem span="3">'
        '<div class="sidebar"><div class="logo" '
        'style="background: red; text-align: left;">  Mi panel  </div></div>'
        '</GridItem><GridItem><div>hola</div></GridItem></Grid></div>'
    )
    with scoped_css_resources(
        ["styles.css"], resolver=lambda _: (
            ".layout {min-height: 100vh}"
            ".sidebar {height: 100vh; background-color: blue; padding: 20px 12px}"
        ),
    ):
        tree = psx(source)
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(800, True), AvailableSize(600, True)),
        engine=PythonLayoutEngine(), argv=["grid-padded-nested-block"],
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(tree)
        def descendants(instance):
            yield instance
            for child in instance.children:
                yield from descendants(child)
        nodes = list(descendants(mounted))
        sidebar = next(x for x in nodes if x.node.css_source is not None
                       and "sidebar" in x.node.css_source.classes)
        logo = next(x for x in nodes if x.node.css_source is not None
                    and "logo" in x.node.css_source.classes)
        assert logo.handle.widget.parentWidget() is sidebar.handle.widget
        logo_rect = logo.handle.widget.geometry()
        assert logo_rect.x() == pytest.approx(12, abs=1)
        assert logo_rect.y() == pytest.approx(20, abs=1)
        assert logo_rect.width() <= sidebar.handle.widget.width() - 24 + 1
        for node in descendants(logo):
            if node is logo or node.handle is None:
                continue
            rect = node.handle.widget.geometry()
            assert rect.x() >= -1
            assert rect.x() + rect.width() <= logo_rect.width() + 1
            if node.node.type == "Text":
                assert rect.x() == pytest.approx(0, abs=1)
    finally:
        reconciler.unmount()


def test_grid_item_css_flex_sidebar_with_nested_buttons_measures_in_qt():
    from psx.css.context import scoped_css_resources
    markup = (
        '<div class="layout"><Grid gap="0px"><GridItem span="3">'
        '<div class="sidebar"><h4>Mi panel</h4>'
        '<div class="sidebar-content"><button>Resumen</button>'
        '<button>Usuarios</button><button>Reportes</button>'
        '<button>Configuración</button></div></div>'
        '</GridItem><GridItem><div class="content">hola</div></GridItem>'
        '</Grid></div>'
    )
    css = (
        '.layout {min-height: 100vh}'
        '.sidebar {height: 100vh; background: #1f2430; '
        'padding: 20px 12px; display: flex; flex-direction: column; gap: 10px}'
        '.sidebar-content {display: flex; flex-direction: column; gap: 10px}'
        '.sidebar-content > button {text-align: left; border: 1px solid #abcdef; '
        'border-radius: 6px}'
    )
    with scoped_css_resources(["css/styles.css"], resolver=lambda _: css):
        tree = psx(markup)
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(800, True), AvailableSize(600, True)),
        engine=PythonLayoutEngine(), argv=["grid-css-flex-sidebar"],
    )
    reconciler = Reconciler(renderer)
    try:
        reconciler.render(tree)
        assert renderer.grid_result is not None
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(1100, True), AvailableSize(700, True)))
        renderer.commit_layout(reconciler.root)
        assert renderer.grid_result is not None
    finally:
        reconciler.unmount()
