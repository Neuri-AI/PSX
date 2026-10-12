"""F3-G2 real Tk external Native/custom geometry; no pack/grid fallback."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import unittest

from psx import Flex, Text
from psx.core.errors import RendererCapabilityError
from psx.core.native import Native
from psx.core.vnode import create_element
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkHandle, TkinterRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.f3_external import SFLEExternalPort
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, Rect


def constraints():
    return LayoutConstraints(AvailableSize(160, True), AvailableSize(80, True))


def port(calls):
    def measure(widget, limits):
        calls.append("measure")
        return IntrinsicSizes(10, 25, 10, 19, 25, 19)
    def apply(widget, rect):
        calls.append(("apply", rect))
        widget.place(
            x=round(rect.x), y=round(rect.y),
            width=round(rect.width), height=round(rect.height),
        )
    def read(widget):
        calls.append("read")
        v = widget.place_info()
        return Rect(*(float(v[axis]) for axis in ("x", "y", "width", "height")))
    return SFLEExternalPort(measure, apply, read)


class TkExternalPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = tk.Tk()
        cls.host.geometry("400x240+0+0")
        cls.host.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.host.destroy()

    def setUp(self):
        self.renderer = TkinterRenderer(
            root=self.host, sfle_constraints=constraints(),
            engine=PythonLayoutEngine(),
        )
        self.tree = Reconciler(self.renderer)
        self.addCleanup(self.renderer.close)
        self.addCleanup(self.tree.unmount)

    def test_native_ttk_widget_is_measured_placed_and_read_back(self):
        calls = []
        native = Native(ttk.Label, renderer="tkinter", sfle_port=port(calls),
                        key="native", layout_width="35px", layout_height="18px",
                        flex_basis="35px", flex_shrink=0)
        root = self.tree.render(Flex(
            Text("Leading", key="text", layout_width="20px",
                 layout_height="18px", flex_basis="20px", flex_shrink=0),
            native, gap=7, width=160, height=80, align_items="flex-start",
        ))
        widget = root.children[1].handle.widget
        self.assertIsInstance(widget, ttk.Label)
        self.assertIs(widget.master, root.handle.widget)
        self.assertEqual(widget.winfo_manager(), "place")
        self.assertEqual(
            tuple(round(float(widget.place_info()[axis])) for axis in
                  ("x", "y", "width", "height")), (27, 0, 35, 18),
        )
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(27, 0, 35, 18)), calls)
        self.assertIn("read", calls)
        self.assertEqual(root.handle.widget.pack_slaves(), [])
        self.assertEqual(root.handle.widget.grid_slaves(), [])

    def test_registered_tk_custom_leaf_uses_explicit_port(self):
        calls = []
        class Adapter:
            sfle_port = port(calls)
            def create(self, renderer, node, parent):
                return TkHandle("CustomBadge", ttk.Label(parent.widget, text="Badge"), {})
            def update(self, renderer, handle, changed, removed):
                pass
            def destroy(self, renderer, handle):
                handle.widget.destroy()
            def bind_event(self, renderer, handle, event, slot):
                raise RendererCapabilityError("Unknown custom event")
            def unbind_event(self, renderer, subscription):
                pass
        self.renderer.register_adapter("CustomBadge", Adapter())
        root = self.tree.render(Flex(
            create_element("CustomBadge", layout_width="32px",
                           layout_height="18px", flex_basis="32px", flex_shrink=0),
            width=160, height=80,
        ))
        widget = root.children[0].handle.widget
        self.assertIs(widget.master, root.handle.widget)
        self.assertEqual(widget.winfo_manager(), "place")
        self.assertEqual(
            tuple(round(float(widget.place_info()[a])) for a in
                  ("x", "y", "width", "height")), (0, 0, 32, 18),
        )
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(0, 0, 32, 18)), calls)
        self.assertIn("read", calls)

    def test_unported_native_fails_before_tk_factory(self):
        calls = []
        def factory(parent):
            calls.append("factory")
            return ttk.Label(parent)
        with self.assertRaisesRegex(RendererCapabilityError, "Native requires"):
            self.tree.render(Flex(
                Native(factory, renderer="tkinter", layout_width="20px"),
                width=160, height=80,
            ))
        self.assertEqual(calls, [])

    def test_borrowed_tk_widget_with_foreign_parent_fails_without_disposal(self):
        from psx.core.native import NativeWidget, NativeOwnership
        from psx.core.vnode import native_widget
        parent = ttk.Frame(self.host)
        widget = ttk.Label(parent, text="Caller widget")
        declaration = NativeWidget(
            renderer="tkinter", widget=widget,
            ownership=NativeOwnership.BORROWED,
            sfle_port=port([]),
        )
        with self.assertRaisesRegex(RendererCapabilityError, "does not support reparenting"):
            self.tree.render(Flex(
                native_widget(declaration, key="borrowed",
                              layout_width="32px", layout_height="18px",
                              flex_basis="32px", flex_shrink=0),
                width=160, height=80,
            ))
        self.assertTrue(widget.winfo_exists())
        self.assertIs(widget.master, parent)
        self.assertEqual(widget.cget("text"), "Caller widget")
        widget.destroy()
        parent.destroy()

