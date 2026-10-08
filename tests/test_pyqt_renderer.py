from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class PyQtRendererSubprocessTests(unittest.TestCase):
    """Qt bindings run in isolated processes and must never be mixed."""

    def _exercise(self, binding: str) -> None:
        environment = dict(os.environ)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent(
            f"""
            from psx import App, Button, Column, Text, component, use_state

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
            """
        )
        result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pyqt6_counter_preserves_button_identity(self) -> None:
        self._exercise("pyqt6")

    def test_pyqt5_counter_preserves_button_identity(self) -> None:
        self._exercise("pyqt5")
