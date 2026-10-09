from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivyRendererSubprocessTests(unittest.TestCase):
    def test_counter_preserves_button_identity_and_uses_clock_scheduler(self) -> None:
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1"})
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent(
            """
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from psx import App, Button, Checkbox, Column, Text, component, use_state

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
            from kivy.uix.label import Label
            from psx.core.reconcile import Reconciler
            r = Reconciler(app.renderer)
            root = r.render(Column(Text("old", font_size=24, bold=True, italic=True,
                                        color="#336699", align="right", enabled=False)))
            label = root.children[0].handle.widget
            assert isinstance(label, Label) and label.text == "old"
            assert label.font_size == 24 and label.bold and label.italic and label.disabled
            assert label.halign == "right"
            assert list(label.color) == [0.2, 0.4, 0.6, 1]
            r.render(Column(Text("new", font_size=12, color="#112233", align="center")))
            assert r.root.children[0].handle.widget is label and label.text == "new"
            assert label.font_size == 12 and not label.bold and not label.italic and not label.disabled
            assert label.halign == "center"
            assert list(label.color) == [17/255, 34/255, 51/255, 1]
            r.render(Column(Text("theme")))
            assert list(label.color) == list(label.property("color").defaultvalue)
            assert list(label.disabled_color) == list(label.property("disabled_color").defaultvalue)
            label.size = (300, 60)
            assert tuple(label.text_size) == (300, 60)
            r.render(Column())
            assert label.parent is None and r.root.handle.children == []
            label.size = (400, 80)
            assert tuple(label.text_size) == (300, 60)  # size subscription cleaned up
            r.unmount()
            changes = []
            r = Reconciler(app.renderer)
            check = r.render(Checkbox(on_change=changes.append)).handle.widget
            check.active = True
            assert changes == [True]
            r.render(Checkbox(checked=True, on_change=changes.append))
            assert r.root.handle.widget is check and check.active
            r.unmount()
            """
        )
        result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
        if "Unable to get a Window" in result.stderr or "Unable to get a Window" in result.stdout:
            self.skipTest("Kivy is installed but this test host has no usable native window provider.")
        self.assertEqual(result.returncode, 0, result.stderr)
