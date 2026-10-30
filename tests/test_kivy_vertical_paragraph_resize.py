"""Regression for a bare HTML paragraph during Kivy vertical window resize."""

from __future__ import annotations

import pytest

pytest.importorskip("kivy")

from psx import psx
from psx.core.reconcile import Reconciler
from psx.renderers.kivy.kivy import KivyRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


def _viewport(width, height):
    return LayoutConstraints(
        AvailableSize(width, True),
        AvailableSize(height, True),
    )


def test_html_paragraph_does_not_pulse_during_vertical_resize():
    """div > p > Text has no Scroll or Grid; text height is intrinsic."""
    renderer = KivyRenderer(
        sfle_constraints=_viewport(900, 400),
        engine=PythonLayoutEngine(),
    )
    tree = Reconciler(renderer)
    try:
        root = tree.render(psx('''
            <div class="layout">
                <p style="background:blue; font-size: 30px;">Hola</p>
            </div>
        '''))
        assert root.node.type == "div"
        assert root.children[0].node.type == "p"
        assert root.children[0].children[0].node.type == "Text"
        paragraph = root.children[0].handle.widget
        label = root.children[0].children[0].handle.widget
        original = (paragraph.height, label.height, label.font_size)
        assert original[0] > 0
        assert original[1] > 0
        assert tuple(label.text_size)[1] is None

        # Unlike legacy Kivy Label, a Cinnamon Text may not let the native
        # widget's *height* set the text layout height. That creates a
        # feedback loop when resizing the top-level window vertically.
        text_size = tuple(label.text_size)
        native_size = tuple(label.size)
        label.size = (native_size[0], native_size[1] + 24)
        assert tuple(label.text_size) == text_size
        label.size = native_size

        for height in (380, 240, 620, 180, 730, 260, 400):
            renderer.set_sfle_constraints(_viewport(900, height))
            renderer.commit_layout(root)
            assert paragraph.height == pytest.approx(original[0], abs=1 / 64)
            assert label.height == pytest.approx(original[1], abs=1 / 64)
            assert label.font_size == pytest.approx(original[2])
            assert tuple(label.text_size) == text_size
            cache = renderer._sfle_native_intrinsic_cache
            assert id(label) not in cache.last_measured
            assert not any(entry[0] == id(label) for entry in cache.last_width_measured)
            assert renderer.sfle_result.geometry_commit_error <= 1
            assert root.children[0].handle.widget is paragraph
            assert root.children[0].children[0].handle.widget is label
    finally:
        tree.unmount()
