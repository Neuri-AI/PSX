from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivyRendererSubprocessTests(unittest.TestCase):
    def test_counter_preserves_button_identity_and_uses_clock_scheduler(self) -> None:
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_WINDOW": "mock"})
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent(
            """
            from kivy.clock import Clock
            from psx import App, Button, Column, Text, component, use_state

            @component
            def Counter():
                value, set_value = use_state(0)
                return Column(Text(str(value), key="text"), Button("+", key="button", on_click=lambda: set_value(value + 1)))

            app = App(Counter(), renderer="kivy")
            app.mount()
            column = app.reconciler.root.children[0].handle
            label, button = column.children
            native_button = button.widget
            native_button.dispatch("on_release")
            Clock.tick()
            assert label.widget.text == "1"
            assert button.widget is native_button
            app.unmount()
            """
        )
        result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
        if "Unable to get a Window" in result.stderr or "Unable to get a Window" in result.stdout:
            self.skipTest("Kivy is installed but this test host has no usable native window provider.")
        self.assertEqual(result.returncode, 0, result.stderr)
