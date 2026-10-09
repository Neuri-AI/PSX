from __future__ import annotations

import os
import importlib.util
import subprocess
import sys
import textwrap
import unittest


class PyQtRendererSubprocessTests(unittest.TestCase):
    """Qt bindings run in isolated processes and must never be mixed."""

    def _exercise(self, binding: str) -> None:
        if importlib.util.find_spec("PyQt" + binding[-1]) is None:
            self.skipTest(f"Optional {binding} binding is not installed.")
        environment = dict(os.environ)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent(
            f"""
            from psx import App, Button, Checkbox, Column, Text, component, use_state

            @component
            def Counter():
                value, set_value = use_state(0)
                return Column(Text(str(value), key="text"), Button("+", key="button", on_click=lambda: set_value(value + 1)))

            app = App(Counter(), renderer="{binding}")
            app.mount()
            column = app.reconciler.root.children[0].handle
            label, button = (column.layout.itemAt(i).widget() for i in range(2))
            before = button
            button.click()
            app.renderer.application.processEvents()
            assert label.text() == "1"
            assert button is before
            app.unmount()
            from importlib import import_module
            core = import_module("PyQt{binding[-1]}.QtCore")
            widgets = import_module("PyQt{binding[-1]}.QtWidgets")
            from psx.core.reconcile import Reconciler
            r = Reconciler(app.renderer)
            label = r.render(Text("old", font_size=24, bold=True, italic=True,
                                  color="#336699", align="right", enabled=False)).handle.widget
            assert isinstance(label, widgets.QLabel)
            assert label.font().pixelSize() == 24 and label.font().bold() and label.font().italic()
            assert label.styleSheet() == "color: #336699;" and not label.isEnabled()
            enum = getattr(core.Qt, "AlignmentFlag", core.Qt)
            assert label.alignment() & enum.AlignRight
            r.render(Text("new", font_size=12, color="#112233", align="center"))
            assert r.root.handle.widget is label and label.text() == "new"
            assert label.font().pixelSize() == 12 and not label.font().bold() and not label.font().italic()
            assert label.styleSheet() == "color: #112233;" and label.isEnabled()
            assert label.alignment() & enum.AlignHCenter
            r.render(Text("theme"))
            assert label.styleSheet() == ""
            r.unmount()
            changes = []
            r = Reconciler(app.renderer)
            check = r.render(Checkbox(on_change=changes.append)).handle.widget
            check.click()
            assert changes == [True]
            r.render(Checkbox(checked=True, on_change=changes.append))
            assert r.root.handle.widget is check and check.isChecked()
            r.unmount()
            core.QCoreApplication.sendPostedEvents(None, getattr(getattr(core.QEvent, "Type", core.QEvent), "DeferredDelete"))
            sip = import_module("PyQt{binding[-1]}.sip")
            assert sip.isdeleted(label)
            """
        )
        result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pyqt6_counter_preserves_button_identity(self) -> None:
        self._exercise("pyqt6")

    def test_pyqt5_counter_preserves_button_identity(self) -> None:
        self._exercise("pyqt5")
