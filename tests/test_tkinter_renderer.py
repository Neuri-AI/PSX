from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import Button, Checkbox, Flex, Text, component, use_state
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


    def test_flex_has_explicit_flex_route_without_pack_layout_fallback(self) -> None:
        from psx import Flex
        from psx.core.errors import RendererCapabilityError

        self.assertIsNotNone(self.renderer.adapters.get("Flex"))
        with self.assertRaisesRegex(RendererCapabilityError, "Native SFLE SFLE geometry"):
            self.renderer.create(Flex(Text("A")), None)

    def _enable_native_sfle(self) -> None:
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, LayoutConstraints
        native = TkinterRenderer(
            root=self.root,
            sfle_constraints=LayoutConstraints(
                AvailableSize(640, True), AvailableSize(480, True)),
            engine=PythonLayoutEngine(),
        )
        self.renderer = native
        self.reconciler = Reconciler(native)
        self.addCleanup(self.reconciler.unmount)
        self.addCleanup(native.close)

    def test_counter_reuses_ttk_widgets_and_updates_on_the_tk_scheduler(self) -> None:
        self._enable_native_sfle()

        @component
        def Counter():
            count, set_count = use_state(0)
            return Flex(
                Text(f"Count: {count}", key="label"),
                Button("Increment", key="button", on_click=lambda: set_count(lambda value: value + 1)),
                direction="column", width="616px", height="456px",
                padding=12, gap=6,
            )

        root = self.reconciler.render(Counter())
        column = root.children[0]
        label, button = column.children
        label_widget = label.handle.widget
        button_widget = button.handle.widget
        self.assertEqual(label_widget.cget("text"), "Count: 0")
        self.assertIsNotNone(self.renderer.sfle_result)
        self.assertGreater(int(label_widget.place_info()["x"]), 0)
        button_widget.invoke()
        self.renderer.flush()
        self.assertIs(label.handle.widget, label_widget)
        self.assertIs(button.handle.widget, button_widget)
        self.assertEqual(label_widget.cget("text"), "Count: 1")

    def test_keyed_reorder_preserves_widgets_and_sfle_geometry(self) -> None:
        self._enable_native_sfle()

        def view(reverse=False):
            children = (Text("B", key="b"), Text("A", key="a")) if reverse else (
                Text("A", key="a"), Text("B", key="b"),
            )
            return Flex(*children, direction="row", width="640px", height="480px",
                        gap=4, align_items="flex-start")

        first = self.reconciler.render(view())
        a, b = first.children
        a_widget, b_widget = a.handle.widget, b.handle.widget
        self.assertLess(int(a_widget.place_info()["x"]), int(b_widget.place_info()["x"]))
        second = self.reconciler.render(view(True))
        self.assertIs(second.children[0].handle.widget, b_widget)
        self.assertIs(second.children[1].handle.widget, a_widget)
        self.assertLess(int(b_widget.place_info()["x"]), int(a_widget.place_info()["x"]))

    def test_removing_optional_layout_props_reflows_from_sfle_defaults(self) -> None:
        self._enable_native_sfle()

        def view(padding, gap):
            return Flex(
                Flex(Text("Ready"), direction="row", padding=padding, gap=gap,
                     key="inner"),
                direction="column", width="640px", height="480px",
                padding=padding, gap=gap,
            )

        first = self.reconciler.render(view(24, 12))
        outer = first.handle.widget
        inner = first.children[0].handle.widget
        label = first.children[0].children[0].handle.widget
        before = int(label.place_info()["x"])
        self.assertGreater(before, 0)

        second = self.reconciler.render(view(0, 0))
        self.assertIs(second.handle.widget, outer)
        self.assertIs(second.children[0].handle.widget, inner)
        self.assertIs(second.children[0].children[0].handle.widget, label)
        self.assertEqual(int(label.place_info()["x"]), 0)

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
