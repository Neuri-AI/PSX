"""Regression coverage for CSS backgrounds on native Qt form controls."""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "src")

try:
    from PySide6.QtWidgets import QPushButton, QLineEdit
    from psx.css.visual_values import CssColor
    from psx.renderers.qt.pyqt import QtHandle
    from psx.renderers.qt.pyside import PySide6Renderer
except ImportError:
    QPushButton = None


@unittest.skipIf(QPushButton is None, "PySide6 is not installed")
class QtCssControlBackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = PySide6Renderer(argv=["psx-css-background-test"])

    def test_background_color_is_applied_and_cleared_on_button(self):
        widget = QPushButton("Save")
        handle = QtHandle("Button", widget)
        colored = SimpleNamespace(
            specified=frozenset({"background-color"}),
            properties={"background-color": CssColor("#ffffff")},
        )
        default = SimpleNamespace(specified=frozenset(), properties={})
        self.renderer.apply_css(handle, colored)
        self.assertIn("background-color: #ffffff;", widget.styleSheet())
        self.renderer.apply_css(handle, default)
        self.assertNotIn("background-color:", widget.styleSheet())
        widget.deleteLater()

    def test_background_color_is_applied_to_input(self):
        widget = QLineEdit()
        handle = QtHandle("Input", widget)
        colored = SimpleNamespace(
            specified=frozenset({"background-color"}),
            properties={"background-color": CssColor("#333333")},
        )
        self.renderer.apply_css(handle, colored)
        self.assertIn("background-color: #333333;", widget.styleSheet())
        widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
