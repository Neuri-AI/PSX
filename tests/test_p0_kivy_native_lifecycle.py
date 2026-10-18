"""P0 C07 Kivy lifetime probes in isolated native subprocess.

A Kivy window provider is required. CI runs with xvfb-run. No silent
skips for missing native display or SDL2 failures in this certification suite.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivyNativeLifecycleTests(unittest.TestCase):
    def test_native_teardown_callback_and_borrowed_widget_lifetime(self) -> None:
        program = textwrap.dedent(
            """
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.label import Label
            from kivy.uix.boxlayout import BoxLayout

            from psx import Button, Flex, Native, Text, component, use_effect
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(420, True), AvailableSize(320, True)
                ),
                engine=PythonLayoutEngine(),
            )
            r = Reconciler(renderer)
            cleaned = []

            @component
            def Screen():
                def effect():
                    def cleanup():
                        cleaned.append("effect")
                        raise RuntimeError("injected Kivy cleanup failure")
                    return cleanup
                use_effect(effect, [])
                return Flex(Text("Kivy mounted"), direction="column")

            mounted = r.render(Screen())
            owned = mounted.children[0].children[0].handle.widget
            assert owned.parent is not None
            try:
                r.unmount()
            except RuntimeError as exc:
                assert "injected Kivy cleanup failure" in str(exc)
            else:
                raise AssertionError("throwing hook cleanup did not propagate")
            assert cleaned == ["effect"]
            assert owned.parent is None
            assert r.root is None

            for i in range(100):
                tree = r.render(Flex(Text("cycle " + str(i)), direction="column"))
                previous = tree.children[0].handle.widget
                r.unmount()
                assert previous.parent is None, "retained Kivy widget at " + str(i)

            owner = BoxLayout()
            borrowed = Label(text="borrowed")
            original_size_hint = (.6, .4)
            original_pos_hint = {"center_x": .5}
            borrowed.size_hint = original_size_hint
            borrowed.pos_hint = dict(original_pos_hint)
            owner.add_widget(borrowed)
            r.render(Flex(Native(borrowed, key="borrowed"), direction="column"))
            assert borrowed.parent is not owner
            r.unmount()
            assert borrowed.parent is owner
            assert borrowed.size_hint == original_size_hint
            assert borrowed.pos_hint == original_pos_hint

            calls = []
            leaf = r.render(Button("Press", on_click=lambda: calls.append("click")))
            button = leaf.handle.widget
            slot = leaf.event_slots["on_click"][0]
            button.dispatch("on_release")
            assert calls == ["click"]
            r.unmount()
            assert slot.invoke() is None
            assert button.parent is None
            print("P0 Kivy native lifetime assertions passed")
            """
        )
        env = dict(os.environ)
        env["KIVY_NO_FILELOG"] = "1"
        env["KIVY_NO_ARGS"] = "1"
        env["PYTHONPATH"] = os.pathsep.join(filter(None, ("src", env.get("PYTHONPATH", ""))))
        result = subprocess.run(
            [sys.executable, "-c", program], env=env, text=True,
            capture_output=True, timeout=90, check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Kivy native lifetime subprocess exited {result.returncode}:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        self.assertIn("P0 Kivy native lifetime assertions passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
