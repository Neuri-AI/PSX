from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import Button, Checkbox, Column, Row, Text, component, use_state
from psx.core.reconcile import Reconciler
from psx.integrations.qyro import mount_psx
from psx.renderers.tkinter import TkinterRenderer


class TkinterRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import tkinter as tk
        # Reuse one Tcl/Tk interpreter, as an embedded Qyro app does. Repeated
        # interpreter creation can fail intermittently in Windows Conda builds.
        cls.root = tk.Tk()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def setUp(self) -> None:
        self.renderer = TkinterRenderer(root=self.root)
        self.renderer.root.withdraw()
        self.addCleanup(self.renderer.close)
        self.reconciler = Reconciler(self.renderer)
        self.addCleanup(self.reconciler.unmount)

    def test_counter_reuses_ttk_widgets_and_updates_on_the_tk_scheduler(self) -> None:
        @component
        def Counter():
            count, set_count = use_state(0)
            return Column(
                Text(f"Count: {count}", key="label"),
                Button("Increment", key="button", on_click=lambda: set_count(lambda value: value + 1)),
                padding=12,
                spacing=6,
            )

        root = self.reconciler.render(Counter())
        column = root.children[0]
        label, button = column.children
        label_widget = label.handle.widget
        button_widget = button.handle.widget
        self.assertEqual(label_widget.cget("text"), "Count: 0")
        self.assertEqual(tuple(column.handle.widget.cget("padding")), (12,))
        button_widget.invoke()
        self.renderer.flush()
        self.assertIs(label.handle.widget, label_widget)
        self.assertIs(button.handle.widget, button_widget)
        self.assertEqual(label_widget.cget("text"), "Count: 1")

    def test_keyed_reorder_preserves_widgets_and_pack_order(self) -> None:
        first = self.reconciler.render(Row(Text("A", key="a"), Text("B", key="b"), spacing=4))
        a, b = first.children
        a_widget, b_widget = a.handle.widget, b.handle.widget
        second = self.reconciler.render(Row(Text("B", key="b"), Text("A", key="a"), spacing=4))
        self.assertIs(second.children[0].handle.widget, b_widget)
        self.assertIs(second.children[1].handle.widget, a_widget)
        self.assertEqual(second.handle.widget.pack_slaves(), [b_widget, a_widget])

    def test_removing_optional_layout_props_resets_defaults(self) -> None:
        first = self.reconciler.render(
            Column(Row(Text("Ready"), padding=8, spacing=4), padding=24, spacing=12)
        )
        column_widget = first.handle.widget
        row_widget = first.children[0].handle.widget

        second = self.reconciler.render(Column(Row(Text("Ready"))))

        self.assertIs(second.handle.widget, column_widget)
        self.assertIs(second.children[0].handle.widget, row_widget)
        self.assertEqual(tuple(column_widget.cget("padding")), (0,))
        self.assertEqual(tuple(row_widget.cget("padding")), (0,))

    def test_worker_state_update_waits_for_tk_ui_drain(self) -> None:
        holder: dict[str, object] = {}

        @component
        def Counter():
            count, set_count = use_state(0)
            holder["set_count"] = set_count
            return Text(str(count))

        root = self.reconciler.render(Counter())
        label = root.children[0].handle.widget
        worker = threading.Thread(target=lambda: holder["set_count"](1))
        worker.start()
        worker.join()
        self.assertEqual(label.cget("text"), "0")
        self.renderer.flush()
        self.assertEqual(label.cget("text"), "1")

    def test_mount_psx_borrows_a_tk_host_without_destroying_it(self) -> None:
        mounted = mount_psx(self.renderer.root, Text("embedded"), renderer=self.renderer)
        self.assertIn(mounted.widget, self.renderer.root.pack_slaves())
        mounted.unmount()
        self.assertEqual(self.renderer.root.pack_slaves(), [])
        self.assertTrue(self.renderer.root.winfo_exists())

    def test_text_portable_update_and_clean_destruction(self) -> None:
        from tkinter import ttk
        from tkinter.font import Font
        label = self.reconciler.render(Text("old", font_size=24, bold=True, italic=True,
                                             color="#336699", align="right", enabled=False)).handle.widget
        self.assertIsInstance(label, ttk.Label)
        font = Font(root=label, font=label.cget("font"))
        self.assertEqual(int(label.tk.splitlist(label.cget("font"))[1]), -24)
        self.assertEqual(font.actual("weight"), "bold")
        self.assertEqual(font.actual("slant"), "italic")
        self.assertEqual(str(label.cget("foreground")), "#336699")
        self.assertEqual(str(label.cget("anchor")), "e")
        self.assertTrue(label.instate(("disabled",)))
        self.reconciler.render(Text("new", font_size=12, color="#112233", align="center"))
        self.assertIs(self.reconciler.root.handle.widget, label)
        self.assertEqual(label.cget("text"), "new")
        font = Font(root=label, font=label.cget("font"))
        self.assertEqual(int(label.tk.splitlist(label.cget("font"))[1]), -12)
        self.assertEqual(font.actual("weight"), "normal")
        self.assertEqual(font.actual("slant"), "roman")
        self.assertEqual(str(label.cget("foreground")), "#112233")
        self.assertEqual(str(label.cget("anchor")), "center")
        self.assertTrue(label.instate(("!disabled",)))
        self.reconciler.render(Text("theme"))
        self.assertEqual(str(label.cget("foreground")), "")
        self.reconciler.unmount()
        self.assertFalse(label.winfo_exists())

    def test_checkbox_updates_reuses_widget_and_unbinds(self) -> None:
        calls: list[bool] = []
        widget = self.reconciler.render(Checkbox(on_change=calls.append)).handle.widget
        widget.invoke()
        self.assertEqual(calls, [True])
        self.reconciler.render(Checkbox(checked=True, enabled=False, on_change=calls.append))
        self.assertIs(self.reconciler.root.handle.widget, widget)
        self.assertTrue(widget._psx_variable.get())
        self.assertTrue(widget.instate(("disabled",)))
        self.reconciler.unmount()
        self.assertFalse(widget.winfo_exists())
