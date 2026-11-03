import os

from psx import psx
from psx.core.reconcile import Reconciler
from tests.test_mounted_grid_native_renderers import make_renderer


def test_css_auto_inline_margins_center_block():
    backend = os.environ['PSX_GRID_BACKEND']
    renderer, close = make_renderer(backend)
    tree = Reconciler(renderer)
    try:
        root = tree.render(psx('<div><div style="width:100px; margin:0 auto"><p>Centered</p></div></div>'))
        widget = root.children[0].handle.widget
        parent = root.handle.widget
        if backend == 'qt':
            left, w, total = widget.x(), widget.width(), parent.width()
        elif backend == 'tk':
            left = float(widget.place_info()['x'])
            w = float(widget.place_info()['width'])
            total = renderer._sfle_constraints.width.value
        else:
            left, w, total = widget.x, widget.width, parent.width
        assert abs(left - (total - w) / 2) <= 1
    finally:
        tree.unmount()
        close()
