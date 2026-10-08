from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import Button, Column, Row, Text, component, use_state
from psx.core.reconcile import Reconciler
from psx.integrations.qyro import mount_psx
from psx.renderers.tkinter import TkinterRenderer


class TkinterRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = TkinterRenderer()
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


if __name__ == "__main__":
    unittest.main()
