"""P0 C07 — real Tk lifecycle and callback retirement.

Run on a host with a Tk display, e.g. xvfb-run -a python -m pytest -q
tests/test_p0_tkinter_native_lifecycle.py. No assumptions about RSS.
"""
from __future__ import annotations

import tkinter as tk
import unittest

from psx import Button, Text, component, use_effect
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter import TkinterRenderer


class TkNativeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def setUp(self) -> None:
        self.renderer = TkinterRenderer(root=self.root)
        self.reconciler = Reconciler(self.renderer)

    def tearDown(self) -> None:
        self.reconciler.unmount()
        self.renderer.close()

    def test_throwing_effect_releases_native_widget(self) -> None:
        cleaned: list[str] = []

        @component
        def Screen():
            def effect():
                def cleanup():
                    cleaned.append("cleanup")
                    raise RuntimeError("injected Tk cleanup failure")
                return cleanup
            use_effect(effect, [])
            return Text("Tk lifetime")

        instance = self.reconciler.render(Screen())
        widget = instance.children[0].handle.widget
        self.assertTrue(widget.winfo_exists())

        with self.assertRaisesRegex(RuntimeError, "injected Tk cleanup failure"):
            self.reconciler.unmount()

        self.assertEqual(cleaned, ["cleanup"])
        self.assertFalse(widget.winfo_exists())
        self.assertIsNone(self.reconciler.root)

    def test_repeated_mount_unmount_destroys_real_widgets(self) -> None:
        for i in range(100):
            widget = self.reconciler.render(Text(f"iteration {i}")).handle.widget
            self.reconciler.unmount()
            self.assertFalse(widget.winfo_exists(), f"widget retained at cycle {i}")

    def test_event_slot_inert_and_polling_cancelled(self) -> None:
        calls: list[str] = []
        root = self.reconciler.render(Button("Submit", on_click=lambda: calls.append("clicked")))
        widget = root.handle.widget
        slot = root.event_slots["on_click"][0]
        widget.invoke()
        self.assertEqual(calls, ["clicked"])
        self.reconciler.unmount()
        self.assertIsNone(slot.invoke())
        self.assertFalse(widget.winfo_exists())

        self.renderer.close()
        self.assertTrue(self.renderer._closed)
        self.assertIsNone(self.renderer._after_id)


if __name__ == "__main__":
    unittest.main()
