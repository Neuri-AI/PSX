"""Real pyqtgraph widget in a nested Grid remains measurable during refresh."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def test_reloaded_pyqtgraph_native_widget_mounts_inside_css_grid(tmp_path):
    pytest.importorskip("PySide6")
    pytest.importorskip("numpy")
    pytest.importorskip("pyqtgraph")

    from psx.devtools.qyro_reload import _load_updated_class
    from psx.core.reconcile import Reconciler
    from psx.renderers.qt.pyside import PySide6Renderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, LayoutConstraints

    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(1024, True), AvailableSize(720, True)),
        engine=PythonLayoutEngine(), argv=["native-chart-refresh"],
    )
    source = tmp_path / "main.py"
    source.write_text(
        "import numpy as np\n"
        "import pyqtgraph as pg\n"
        "from PySide6 import QtWidgets\n"
        "from psx import psx\n"
        "class LineChart(pg.PlotWidget):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        x = np.linspace(0, 20, 1000)\n"
        "        self.plot(x, np.sin(x))\n"
        "        self.setMinimumHeight(250)\n"
        "        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, "
        "QtWidgets.QSizePolicy.Policy.Expanding)\n"
        "class AppRoot:\n"
        "    def render(self):\n"
        "        return psx('''<div><Grid gap=\"0px\">"
        "<GridItem span=\"3\"><div>Sidebar</div></GridItem>"
        "<Scroll direction=\"vertical\" height=\"100vh\"><GridItem>"
        "<div class=\"content\"><Grid gap=\"16px\"><GridItem>"
        "<div class=\"card\" style=\"padding: 16px; border: 1px solid #e0e0e0; max-height: 250px;\">"
        "<Native widget={LineChart} key=\"line-chart\" />"
        "</div></GridItem></Grid></div></GridItem></Scroll>"
        "</Grid></div>''')\n",
        encoding="utf-8",
    )
    AppRoot = type("AppRoot", (), {"render": lambda self: None})
    candidate = _load_updated_class(source, AppRoot, frozenset())
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(candidate.render(AppRoot()))
        assert root is not None
        assert renderer.grid_result is not None
        def find_native(instance):
            if instance.node.kind.value == "native":
                return instance
            for child in instance.children:
                found = find_native(child)
                if found is not None:
                    return found
            return None
        native = find_native(root)
        assert native is not None
        parent = native.handle.widget.parentWidget()
        child_box = native.handle.widget.geometry()
        assert child_box.x() >= 16
        assert child_box.x() + child_box.width() <= parent.width() - 17 + 1
        assert parent.height() <= 284 + 1
        assert child_box.y() >= 17 - 1
        assert child_box.y() + child_box.height() <= parent.height() - 17 + 1
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(840, True), AvailableSize(620, True)))
        renderer.commit_layout(root)
        child_box = native.handle.widget.geometry()
        assert child_box.x() >= 16
        assert child_box.x() + child_box.width() <= parent.width() - 16
        assert renderer.grid_result is not None
    finally:
        reconciler.unmount()


def test_activity_paragraphs_are_not_clipped_inside_css_flex_rows():
    from psx import psx
    from psx.core.reconcile import Reconciler
    from psx.renderers.qt.pyside import PySide6Renderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, LayoutConstraints

    renderer = PySide6Renderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(520, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(), argv=["qt-activity-paragraphs"],
    )
    markup = (
        '<div><Grid><GridItem><div class="activity-card">'
        '<h5>Actividad Reciente</h5>'
        '<div style="display:flex; flex-direction:row; justify-content:space-between;'
        ' align-items:center; gap:10px; padding:16px 20px">'
        '<p style="font-size:14px">Ana López creó un reporte</p>'
        '<p style="font-size:14px; min-width:120px">23 de Octubre 10:00 AM</p>'
        '</div>'
        '<div style="display:flex; flex-direction:row; justify-content:space-between;'
        ' align-items:center; gap:10px; padding:16px 20px">'
        '<p style="font-size:14px">Carlos Pérez actualizó un pedido</p>'
        '<p style="font-size:14px; min-width:120px">23 de Octubre 11:00 AM</p>'
        '</div></div></GridItem></Grid></div>'
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(markup))
        def visit(instance):
            yield instance
            for child in instance.children:
                yield from visit(child)
        labels = [
            instance.handle.widget for instance in visit(root)
            if instance.node.type == "Text"
        ]
        assert len(labels) >= 4
        for label in labels:
            assert label.height() >= label.heightForWidth(label.width()) - 1
        renderer.set_sfle_constraints(LayoutConstraints(
            AvailableSize(430, True), AvailableSize(480, True)))
        renderer.commit_layout(root)
        for label in labels:
            assert label.height() >= label.heightForWidth(label.width()) - 1
    finally:
        reconciler.unmount()
