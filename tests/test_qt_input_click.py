"""Native Qt input click dispatch and teardown regression."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from psx.core.reconcile import Reconciler
    from psx.core.vnode import Input
    from psx.renderers.qt.pyside import PySide6Renderer
except ImportError:
    Qt = QTest = Reconciler = Input = PySide6Renderer = None


@unittest.skipIf(PySide6Renderer is None, "PySide6 unavailable")
class QtInputClickTests(unittest.TestCase):
    def test_click_and_rebind_and_dispose(self):
        renderer = PySide6Renderer(argv=["input-click-test"])
        reconciler = Reconciler(renderer)
        calls = []
        mounted = reconciler.render(Input(value="", on_click=lambda: calls.append("initial")))
        widget = mounted.handle.widget
        widget.show()
        renderer.application.processEvents()
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        self.assertEqual(calls, ["initial"])
        reconciler.render(Input(value="", on_click=lambda: calls.append("updated")))
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        self.assertEqual(calls, ["initial", "updated"])
        reconciler.unmount()


if __name__ == "__main__":
    unittest.main()
