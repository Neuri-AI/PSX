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
        def verify_padding():
            sidebar = reconciler.root.children[0].children[0].children[0]
            content = sidebar.children[1]
            sidebar_box = sidebar.handle.widget.geometry()
            content_box = content.handle.widget.geometry()
            assert content_box.x() == pytest.approx(12, abs=1)
            assert content_box.x() + content_box.width() <= sidebar_box.width() - 12 + 1
            for button in content.children:
                child_box = button.handle.widget.geometry()
                assert child_box.x() >= -1
                assert child_box.x() + child_box.width() <= content_box.width() + 1
        verify_padding()
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(1100, True), AvailableSize(700, True)))
        renderer.commit_layout(reconciler.root)
        assert renderer.grid_result is not None
        verify_padding()
    finally:
        reconciler.unmount()


def test_native_sidebar_button_applies_padding_cursor_and_no_border():
    from psx.css.context import scoped_css_resources
    with scoped_css_resources(["theme.css"], resolver=lambda _: (
        "button {height: 38px; font-size: 14px; padding: 0px 10px; "
        "border: none; cursor: pointer}"
    )):
        tree = psx('<div><Grid><GridItem><button>Resumen</button></GridItem></Grid></div>')
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(), argv=["button-css-edges"],
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(tree)
        button = root.children[0].children[0].children[0].handle.widget
        qss = button.styleSheet().lower()
        assert "padding: 0px 10px 0px 10px;" in qss
        assert "border: none;" in qss
        qt = renderer._qtcore.Qt
        shapes = getattr(qt, "CursorShape", qt)
        assert button.cursor().shape() == shapes.PointingHandCursor
    finally:
        reconciler.unmount()


def test_nested_grid_stacks_after_flex_header_in_grid_item_block_flow():
    from psx.css.context import scoped_css_resources

    markup = (
        '<div class="layout"><Grid gap="0px">'
        '<GridItem span="3"><div class="sidebar">Mi panel</div></GridItem>'
        '<GridItem><div class="content">'
        '<div class="header"><p>Reportes</p><p>Hola, Fredo</p></div>'
        '<Grid gap="16px"><GridItem><h1>Contenido de Reportes</h1></GridItem></Grid>'
        '</div></GridItem></Grid></div>'
    )
    css = (
        '.layout { min-height: 100vh; }'
        '.header { display: flex; flex-direction: row; '
        'justify-content: space-between; align-items: center; '
        'gap: 10px; padding: 16px 20px; background: blue; }'
    )
    with scoped_css_resources(["css/styles.css"], resolver=lambda _: css):
        tree = psx(markup)

    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(800, True), AvailableSize(600, True)),
        engine=PythonLayoutEngine(), argv=["nested-grid-after-flex"],
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(tree)

        def find(instance, css_class=None, node_type=None):
            source = instance.node.css_source
            if (css_class is not None and source is not None
                    and css_class in source.classes):
                return instance
            if node_type is not None and instance.node.type == node_type:
                return instance
            for child in instance.children:
                match = find(child, css_class=css_class, node_type=node_type)
                if match is not None:
                    return match
            return None

        content = find(root, css_class="content")
        header = find(root, css_class="header")
        nested = next(
            child for child in content.children if child.node.type == "Grid"
        )
        assert header.handle.widget.parentWidget() is content.handle.widget
        assert nested.handle.widget.parentWidget() is content.handle.widget

        def verify_vertical_stack():
            header_rect = header.handle.widget.geometry()
            grid_rect = nested.handle.widget.geometry()
            assert header_rect.height() > 0
            assert grid_rect.y() >= header_rect.y() + header_rect.height() - 1
            assert grid_rect.height() > 0
            item = nested.children[0]
            assert item.handle.widget.parentWidget() is nested.handle.widget

        verify_vertical_stack()
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(1060, True), AvailableSize(700, True)))
        renderer.commit_layout(reconciler.root)
        verify_vertical_stack()
    finally:
        reconciler.unmount()


def test_dashboard_cards_fit_padded_content_without_clipping():
    """Nested 12-column Grid must use .container's actual content width."""
    from psx.css.context import scoped_css_resources

    markup = (
        '<div class="layout"><Grid gap="0px">'
        '<GridItem span="3"><div class="sidebar">Navigation</div></GridItem>'
        '<GridItem><div class="content">'
        '<div class="header"><p>Resumen</p><p>Hola, Fredo</p></div>'
        '<div class="container"><Grid gap="16px">'
        '<GridItem span="3"><div class="card"><p>Usuarios</p><p>1248</p></div></GridItem>'
        '<GridItem span="3"><div class="card"><p>Ventas</p><p>3456</p></div></GridItem>'
        '<GridItem span="3"><div class="card"><p>Pedidos</p><p>356</p></div></GridItem>'
        '<GridItem span="3"><div class="card"><p>Pendientes</p><p>12</p></div></GridItem>'
        '</Grid></div></div></GridItem></Grid></div>'
    )
    css = (
        '.content { height: 100vh; }'
        '.header { display: flex; flex-direction: row; justify-content: space-between; '
        'padding: 16px 20px; border-bottom: 1px solid #ccc; }'
        '.container { padding: 16px; }'
        '.card { background: #fff; padding: 16px; border: 1px solid #e0e0e0; }'
    )
    with scoped_css_resources(["css/styles.css"], resolver=lambda _: css):
        tree = psx(markup)
    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(1100, True), AvailableSize(700, True)),
        engine=PythonLayoutEngine(), argv=["dashboard-grid-padded-container"],
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(tree)

        def find_class(instance, name):
            source = instance.node.css_source
            if source is not None and name in source.classes:
                return instance
            for child in instance.children:
                found = find_class(child, name)
                if found is not None:
                    return found
            return None

        container = find_class(root, "container")
        cards = find_class(root, "card")
        grid = next(child for child in container.children if child.node.type == "Grid")
        assert cards is not None
        assert grid.handle.widget.width() <= container.handle.widget.width() - 32 + 1
        for item in grid.children:
            rect = item.handle.widget.geometry()
            assert rect.x() >= -1
            assert rect.x() + rect.width() <= grid.handle.widget.width() + 1
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(960, True), AvailableSize(700, True)))
        renderer.commit_layout(root)
        for item in grid.children:
            rect = item.handle.widget.geometry()
            assert rect.x() + rect.width() <= grid.handle.widget.width() + 1
    finally:
        reconciler.unmount()


def test_grid_accepts_scroll_wrapped_item_and_resizes_viewport():
    from psx.css.context import scoped_css_resources

    markup = (
        '<div class="layout"><Grid gap="0px">'
        '<GridItem span="3"><div class="sidebar">Mi panel</div></GridItem>'
        '<Scroll direction="vertical" height="100vh"><GridItem>'
        '<div class="content"><div class="header"><p>Resumen</p></div>'
        '<div class="container"><Grid gap="16px">'
        '<GridItem span="6"><div class="card">Usuarios</div></GridItem>'
        '<GridItem span="6"><div class="card">Ventas</div></GridItem>'
        '</Grid></div></div>'
        '</GridItem></Scroll></Grid></div>'
    )
    css = (
        '.layout { min-height: 100vh }'
        '.container { padding: 16px }'
        '.content { min-height: 130vh }'
    )
    with scoped_css_resources(["css/styles.css"], resolver=lambda _: css):
        tree = psx(markup)
    grid = tree.children[0]
    assert grid.type == "Grid"
    assert [child.type for child in grid.children] == ["GridItem", "GridItem"]
    scrolling_slot = grid.children[1]
    assert scrolling_slot.children[0].type == "Scroll"
    assert scrolling_slot.children[0].children[0].type == "div"

    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(960, True), AvailableSize(600, True)),
        engine=PythonLayoutEngine(), argv=["grid-scroll-viewport"],
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(tree)
        def descendants(instance):
            yield instance
            for child in instance.children:
                yield from descendants(child)
        host = next(instance.handle.widget for instance in descendants(mounted)
                    if instance.node.type == "Scroll")
        assert host.height() == pytest.approx(600, abs=1)
        assert host.width() > 0
        assert host._psx_content.height() >= host.height()
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(1100, True), AvailableSize(750, True)))
        renderer.commit_layout(mounted)
        assert host.height() == pytest.approx(750, abs=1)
        assert host._psx_content.height() >= host.height()
    finally:
        reconciler.unmount()
