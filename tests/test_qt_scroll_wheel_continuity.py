"""Qt Scroll keeps phased trackpad input responsive across long wheel sessions."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def _area():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QWidget
    from psx.renderers.qt.scroll import _scroll_area_class
    from psx.renderers.components.scroll import scroll_props

    app = QApplication.instance() or QApplication(["scroll-wheel-test"])
    area = _scroll_area_class("PySide6")()
    content = QWidget()
    area.setWidget(content)
    area._psx_content = content
    area._psx_sfle_scroll = True
    area.configure(scroll_props({"direction": "vertical", "height": 240}))
    area.resize(320, 240)
    area._psx_content.resize(320, 1600)
    area.verticalScrollBar().setRange(0, 1360)
    return app, area


def test_fractional_trackpad_steps_accumulate_instead_of_freezing():
    app, area = _area()
    try:
        bar = area.verticalScrollBar()
        for _ in range(20):
            assert area._psx_scroll_delta(0.0, 0.4) == (0.0, 0.0)
        assert bar.value() == 8
        for _ in range(20):
            area._psx_scroll_delta(0.0, -0.4)
        assert bar.value() == 0
        app.processEvents()
        for _ in range(10):
            area._psx_scroll_delta(0.0, 0.4)
        assert bar.value() == 4
    finally:
        area.close()
        area.deleteLater()
        app.processEvents()


def test_repeated_boundary_scrolling_does_not_block_resumed_direction():
    app, area = _area()
    try:
        bar = area.verticalScrollBar()
        for _ in range(200):
            area._psx_scroll_delta(0.0, 30.0)
        assert bar.value() == bar.maximum()
        for _ in range(20):
            area._psx_scroll_delta(0.0, 0.4)
        assert bar.value() == bar.maximum()
        from PySide6.QtTest import QTest
        QTest.qWait(800)
        for _ in range(15):
            area._psx_scroll_delta(0.0, -0.4)
        assert bar.value() <= bar.maximum() - 6
        for _ in range(20):
            area._psx_scroll_delta(0.0, 0.4)
        assert bar.value() > 0
        assert area._fade.isActive()
    finally:
        area.close()
        area.deleteLater()
        app.processEvents()


def test_reconfigure_disabling_scroll_discards_fractional_input():
    app, area = _area()
    try:
        from psx.renderers.components.scroll import scroll_props
        area._psx_scroll_delta(0.0, 0.4)
        assert area._psx_subpixel_remainder["y"] != 0.0
        area.configure(scroll_props({"direction": "vertical", "enabled": False}))
        assert area._psx_subpixel_remainder == {"x": 0.0, "y": 0.0}
        area.configure(scroll_props({"direction": "vertical", "enabled": True}))
        for _ in range(3):
            area._psx_scroll_delta(0.0, 0.4)
        assert area.verticalScrollBar().value() == 1
    finally:
        area.close()
        area.deleteLater()
        app.processEvents()
