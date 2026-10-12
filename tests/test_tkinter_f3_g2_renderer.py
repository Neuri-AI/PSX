"""G2 native Tkinter SFLE: real ttk geometry and no pack/grid fallbacks."""
from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import ttk
import unittest

from psx import Button, Checkbox, Flex, Text, component, psx, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutResult


def constraints(width=160, height=80):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))


def item(label, key, width):
    return Button(label, key=key, layout_width=f"{width}px",
                  layout_height="20px", flex_basis=f"{width}px", flex_shrink=0)


def rect(widget):
    """Native place coordinates; meaningful even on an unmapped Tcl widget."""
    placement = widget.place_info()
    return tuple(round(float(placement[axis])) for axis in ("x", "y", "width", "height"))


class TkSFLEGeometryTests(unittest.TestCase):
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
            root=self.host, sfle_constraints=constraints(), engine=PythonLayoutEngine(),
        )
        self.reconciler = Reconciler(self.renderer)
        self.addCleanup(self.renderer.close)
        self.addCleanup(self.reconciler.unmount)

    def test_real_ttk_widgets_use_sfle_place_not_pack_or_grid(self):
        root = self.reconciler.render(Flex(
            Text("Left", key="left", layout_width="40px", layout_height="20px",
                 flex_basis="40px", flex_shrink=0),
            item("Right", "right", 30),
            direction="row", gap=8, width="160px", height="80px",
            align_items="flex-start",
        ))
        frame = root.handle.widget
        left, right = (child.handle.widget for child in root.children)
        self.assertIsInstance(frame, ttk.Frame)
        self.assertIsInstance(left, ttk.Label)
        self.assertIsInstance(right, ttk.Button)
        self.assertEqual(frame.winfo_manager(), "place")
        self.assertEqual(rect(frame), (0, 0, 160, 80))
        self.assertEqual(rect(left), (0, 0, 40, 20))
        self.assertEqual(rect(right), (48, 0, 30, 20))
        self.assertEqual(frame.pack_slaves(), [])
        self.assertEqual(frame.grid_slaves(), [])
        self.assertEqual(left.master, frame)
        self.assertEqual(right.master, frame)
        self.assertEqual(self.renderer.sfle_result.geometry_commit_error, 0.0)
        self.assertEqual(len(self.renderer.sfle_result.boxes), 3)

    def test_nested_psx_markup_parent_relative_geometry_and_css_padding(self):
        root = self.reconciler.render(psx("""
            <Flex direction="column" width="140px" height="60px"
                  padding={10} align_items="flex-start">
                <Flex direction="row" width="120px" height="40px"
                      gap={6} align_items="flex-start">
                    <Button label="A" key="a" layout_width="30px"
                            layout_height="15px" flex_basis="30px"
                            flex_shrink={0}/>
                    <Button label="B" key="b" layout_width="20px"
                            layout_height="15px" flex_basis="20px"
                            flex_shrink={0}/>
                </Flex>
            </Flex>
        """))
        outer = root.handle.widget
        inner = root.children[0].handle.widget
        a, b = (child.handle.widget for child in root.children[0].children)
        self.assertEqual(rect(outer), (0, 0, 160, 80))
        self.assertEqual(rect(inner), (10, 10, 120, 40))
        self.assertEqual(rect(a), (0, 0, 30, 15))
        self.assertEqual(rect(b), (36, 0, 20, 15))
        self.assertIs(inner.master, outer)
        self.assertIs(a.master, inner)
        self.assertIs(b.master, inner)
        for widget in (outer, inner, a, b):
            self.assertEqual(widget.winfo_manager(), "place")

    def test_keyed_reordering_retains_native_handles_and_updates_sfle_positions(self):
        root = self.reconciler.render(
            Flex(item("A", "a", 30), item("B", "b", 20),
                 width=160, height=80, gap=4, align_items="flex-start")
        )
        a, b = (child.handle.widget for child in root.children)
        self.assertEqual((rect(a)[0], rect(b)[0]), (0, 34))
        after = self.reconciler.render(
            Flex(item("B", "b", 20), item("A", "a", 30),
                 width=160, height=80, gap=9, align_items="flex-start")
        )
        self.assertIs(after.children[0].handle.widget, b)
        self.assertIs(after.children[1].handle.widget, a)
        self.assertEqual((rect(b)[0], rect(a)[0]), (0, 29))
        self.assertEqual(self.renderer.sfle_result.generation, 2)
        self.assertEqual(after.handle.children[0].widget, b)
        self.assertEqual(after.handle.children[1].widget, a)

    def test_hooks_events_and_scheduler_commit_without_remounting(self):
        setters = []
        clicked = []

        @component
        def Counter():
            value, setter = use_state(0)
            setters.append(setter)
            return Flex(
                Button("Increment", on_click=lambda: clicked.append(value),
                       key="action", layout_width=f"{20 + 10 * value}px",
                       layout_height="20px", flex_basis=f"{20 + 10 * value}px",
                       flex_shrink=0),
                width=160, height=80,
            )

        root = self.reconciler.render(Counter())
        button = root.children[0].children[0].handle.widget
        self.assertEqual(rect(button)[2], 20)
        button.invoke()
        self.assertEqual(clicked, [0])
        setters[-1](2)
        self.renderer.flush()
        self.assertIs(root.children[0].children[0].handle.widget, button)
        self.assertEqual(rect(button)[2], 40)
        button.invoke()
        self.assertEqual(clicked, [0, 2])

    def test_viewport_resize_reuses_native_widgets_and_explicit_root_geometry(self):
        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
            align_items="flex-start",
        ))
        frame, child = root.handle.widget, root.children[0].handle.widget
        initial = self.renderer.sfle_result.generation
        self.renderer.set_sfle_constraints(constraints(240, 120))
        self.renderer.commit_layout(root)
        self.assertIs(frame, root.handle.widget)
        self.assertIs(child, root.children[0].handle.widget)
        self.assertEqual(rect(frame), (0, 0, 240, 120))
        self.assertEqual(rect(child), (0, 0, 30, 20))
        self.assertGreater(self.renderer.sfle_result.generation, initial)

    def test_real_tk_host_configure_automatically_reflows_sfle(self):
        class CountingEngine:
            def __init__(self):
                self.calls = 0
            def compute(self, snapshot):
                self.calls += 1
                return PythonLayoutEngine().compute(snapshot)

        engine = CountingEngine()
        self.renderer._sfle_engine = engine
        root = self.reconciler.render(Flex(
            item("Left", "left", 30), item("Right", "right", 20),
            width="100%", height="100%", direction="row",
            justify_content="space-between", align_items="flex-start",
        ))
        frame = root.handle.widget
        left, right = (child.handle.widget for child in root.children)
        self.assertEqual(engine.calls, 1)
        self.assertEqual(rect(right), (140, 0, 20, 20))
        self.assertEqual(rect(frame), (0, 0, 160, 80))
        try:
            # A real Tk window Configure event, not set_sfle_constraints().
            self.host.geometry("210x100+0+0")
            self.host.geometry("260x120+0+0")
            self.host.update()
            self.assertIsNone(self.renderer._sfle_resize_error)
            self.assertEqual(
                (self.renderer._sfle_constraints.width.value,
                 self.renderer._sfle_constraints.height.value), (260, 120),
            )
            self.assertEqual(engine.calls, 2)
            self.assertIs(root.children[0].handle.widget, left)
            self.assertIs(root.children[1].handle.widget, right)
            self.assertEqual(rect(frame), (0, 0, 260, 120))
            self.assertEqual(rect(right), (240, 0, 20, 20))
            self.assertEqual(frame.pack_slaves(), [])
            self.assertEqual(frame.grid_slaves(), [])
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)
        finally:
            self.reconciler.unmount()
            self.host.geometry("400x240+0+0")
            self.host.update()

    def test_tk_configure_does_not_commit_after_unmount(self):
        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
        ))
        self.assertIsNotNone(self.renderer._sfle_resize_bind_id)
        self.reconciler.unmount()
        self.assertIsNone(self.renderer._sfle_resize_bind_id)
        try:
            self.host.geometry("280x140+0+0")
            self.host.update()
            self.assertIsNone(self.renderer.sfle_result)
            self.assertIsNone(self.renderer._sfle_mounted_root)
        finally:
            self.host.geometry("400x240+0+0")
            self.host.update()

    def test_rejects_non_sfle_native_geometry_manager(self):
        root = self.reconciler.render(Flex(item("A", "a", 30), width=160, height=80))
        widget = root.children[0].handle.widget
        widget.place_forget()
        widget.pack()
        with self.assertRaises(SFLEError) as captured:
            self.renderer.commit_layout(root)
        self.assertEqual(captured.exception.code, DiagnosticCode.UNSUPPORTED_FEATURE)

    def test_engine_generation_mismatch_rejects_without_native_mutation(self):
        root = self.reconciler.render(Flex(item("A", "a", 30), width=160, height=80))
        widget = root.children[0].handle.widget
        before = rect(widget)

        class WrongGeneration:
            def compute(self, request):
                valid = PythonLayoutEngine().compute(request)
                return LayoutResult(1, request.generation + 1, valid.boxes)

        self.renderer._sfle_engine = WrongGeneration()
        with self.assertRaises(SFLEError) as captured:
            self.renderer.commit_layout(root)
        self.assertEqual(captured.exception.code, DiagnosticCode.INVALID_SNAPSHOT)
        self.assertEqual(rect(widget), before)

    def test_worker_thread_commit_fails_before_any_tcl_calls(self):
        root = self.reconciler.render(Flex(item("A", "a", 30), width=160, height=80))
        errors = []
        def run():
            try:
                self.renderer.commit_layout(root)
            except SFLEError as error:
                errors.append(error)
        worker = Thread(target=run)
        worker.start()
        worker.join()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, DiagnosticCode.UNSUPPORTED_MEASUREMENT)

    def test_unported_builtin_is_explicit_failure_not_native_layout_fallback(self):
        from psx import Image
        with self.assertRaisesRegex(RendererCapabilityError, "not certified"):
            self.reconciler.render(Flex(Image("unported.png"), width=160, height=80))

    def test_additional_tk_native_primitives_have_sfle_geometry_no_pack(self):
        from psx import Slider, ProgressBar, Radio
        # The root content box must agree with the explicitly owned viewport.
        self.renderer.set_sfle_constraints(constraints(440, 80))
        specs = [
            (Checkbox(checked=True, key="cb", layout_width="24px",
                      layout_height="30px", flex_basis="24px", flex_shrink=0), ttk.Checkbutton, 24),
            (Slider(value=25, key="slider", layout_width="100px",
                    layout_height="30px", flex_basis="100px", flex_shrink=0), ttk.Scale, 100),
            (ProgressBar(value=40, key="progress", layout_width="110px",
                         layout_height="30px", flex_basis="110px", flex_shrink=0), ttk.Progressbar, 110),
            (Radio("r", label="Pick", key="radio", layout_width="70px",
                   layout_height="30px", flex_basis="70px", flex_shrink=0), ttk.Radiobutton, 70),
        ]
        root = self.reconciler.render(Flex(
            *(node for node, _, _ in specs),
            width="440px", height="80px", direction="row", gap=6,
            align_items="flex-start",
        ))
        x = 0
        for (node, expected_class, width), instance in zip(specs, root.children):
            widget = instance.handle.widget
            self.assertIsInstance(widget, expected_class)
            self.assertIs(widget.master, root.handle.widget)
            self.assertEqual(widget.winfo_manager(), "place")
            self.assertEqual(rect(widget), (x, 0, width, 30), node.type)
            x += width + 6
        self.assertEqual(len(self.renderer.sfle_result.boxes), 5)
        self.assertTrue(root.children[0].handle.widget._psx_variable.get())

    def test_tk_checkbox_event_and_state_reconciliation_in_sfle_tree(self):
        calls = []
        root = self.reconciler.render(Flex(
            Checkbox(checked=False, key="cb", on_change=calls.append,
                     layout_width="30px", layout_height="20px",
                     flex_basis="30px", flex_shrink=0),
            width=160, height=80,
        ))
        native = root.children[0].handle.widget
        native.invoke()
        self.assertEqual(calls, [True])
        after = self.reconciler.render(Flex(
            Checkbox(checked=True, key="cb", on_change=calls.append,
                     layout_width="55px", layout_height="20px",
                     flex_basis="55px", flex_shrink=0),
            width=160, height=80,
        ))
        self.assertIs(after.children[0].handle.widget, native)
        self.assertEqual(rect(native)[2], 55)
        self.assertTrue(native._psx_variable.get())
        self.assertEqual(calls, [True])

    def test_default_tk_renderer_preserves_g1_fail_closed_route(self):
        regular = TkinterRenderer(root=self.host)
        try:
            with self.assertRaisesRegex(RendererCapabilityError, "F3-G2 SFLE geometry"):
                Reconciler(regular).render(Flex(width=160, height=80))
        finally:
            regular.close()
