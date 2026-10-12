"""G2 native Tkinter SFLE: real ttk geometry and no pack/grid fallbacks."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import struct
import zlib
import tkinter as tk
from tkinter import ttk
import unittest

from psx import Button, Checkbox, Flex, Text, TextArea, component, psx, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutResult


def write_png(path, width, height):
    """Generate deterministic truecolor RGBA pixels without requiring Pillow."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xffffffff,
        )
    rows = (b"\x00" + b"\xff\x33\x66\xff" * width) * height
    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


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

    def test_tk_multiline_text_height_follows_sfle_content_width(self):
        words = ("One two three four five six seven eight nine ten "
                 "eleven twelve thirteen fourteen fifteen sixteen.")
        root = self.reconciler.render(Flex(
            Text(words, key="copy", layout_width="100%", flex_shrink=0),
            item("Below", "below", 30),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        label = root.children[0].handle.widget
        following = root.children[1].handle.widget
        wide_height = rect(label)[3]
        self.assertGreater(wide_height, 0)
        self.assertEqual(rect(following)[1], wide_height)

        self.renderer.set_sfle_constraints(constraints(90, 80))
        self.renderer.commit_layout(root)
        narrow_height = rect(label)[3]
        self.assertGreater(narrow_height, wide_height)
        self.assertEqual(rect(label)[2], 90)
        self.assertEqual(rect(following)[1], narrow_height)
        self.assertEqual(round(float(label.cget("wraplength"))), 90)
        self.assertIs(root.children[0].handle.widget, label)

        self.renderer.set_sfle_constraints(constraints(160, 80))
        self.renderer.commit_layout(root)
        self.assertEqual(rect(label)[3], wide_height)
        self.assertEqual(rect(following)[1], wide_height)
        self.assertEqual(round(float(label.cget("wraplength"))), 160)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_textarea_wraps_at_real_sfle_width_and_preserves_edit_state(self):
        words = ("Alpha bravo charlie delta echo foxtrot golf hotel india "
                 "juliet kilo lima mike november oscar papa quebec romeo sierra tango.")
        events = []
        root = self.reconciler.render(Flex(
            TextArea(value=words, key="edit", on_change=events.append,
                     layout_width="100%", flex_shrink=0),
            item("Below", "below", 30),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        editor, below = (child.handle.widget for child in root.children)
        self.assertIsInstance(editor, tk.Text)
        self.assertEqual(editor.winfo_manager(), "place")
        self.assertEqual(editor.get("1.0", "end-1c"), words)
        wide_height = rect(editor)[3]
        self.assertGreater(wide_height, 0)
        self.assertEqual(rect(below)[1], wide_height)
        editor.mark_set("insert", "1.4")
        editor.tag_add("sel", "1.1", "1.4")
        initial_cursor = editor.index("insert")
        initial_selection = editor.tag_ranges("sel")

        self.renderer.set_sfle_constraints(constraints(90, 500))
        self.renderer.commit_layout(root)
        narrow_height = rect(editor)[3]
        self.assertGreater(narrow_height, wide_height)
        self.assertEqual(rect(editor)[2], 90)
        self.assertEqual(rect(below)[1], narrow_height)
        self.assertEqual(editor.index("insert"), initial_cursor)
        self.assertEqual(editor.tag_ranges("sel"), initial_selection)
        self.assertIs(root.children[0].handle.widget, editor)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)
        self.renderer.set_sfle_constraints(constraints(160, 500))
        self.renderer.commit_layout(root)
        self.assertEqual(rect(editor)[3], wide_height)
        self.assertEqual(rect(below)[1], wide_height)
        self.assertEqual(editor.get("1.0", "end-1c"), words)
        self.assertEqual(events, [])

        editor.insert("end-1c", " " + " ".join(["additional native text"] * 18))
        self.host.update()
        self.assertEqual(events, [editor.get("1.0", "end-1c")])
        self.assertIsNone(self.renderer._sfle_textarea_error)
        self.assertGreater(rect(editor)[3], wide_height)
        self.assertEqual(rect(below)[1], rect(editor)[3])
        self.assertIs(root.children[0].handle.widget, editor)

    def test_textarea_explicit_height_and_callback_rebind(self):
        old, new = [], []
        root = self.reconciler.render(Flex(
            TextArea(value="before", key="editor", on_change=old.append,
                     layout_width="100%", layout_height="36px"),
            item("Below", "below", 30),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        editor = root.children[0].handle.widget
        self.assertEqual(rect(editor)[3], 36)
        after = self.reconciler.render(Flex(
            TextArea(value="before", key="editor", on_change=new.append,
                     layout_width="100%", layout_height="36px"),
            item("Below", "below", 30),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        self.assertIs(after.children[0].handle.widget, editor)
        self.renderer.set_sfle_constraints(constraints(90, 100))
        self.renderer.commit_layout(after)
        self.assertEqual(rect(editor)[3], 36)
        self.assertEqual(rect(after.children[1].handle.widget)[1], 36)
        editor.insert("end-1c", "!")
        self.host.update()
        self.assertEqual(old, [])
        self.assertEqual(new, [editor.get("1.0", "end-1c")])
        self.assertEqual(rect(editor)[3], 36)

    def test_tk_scaling_does_not_multiply_native_place_rectangles(self):
        from psx.sfle.native_pixel_space import DevicePixelSpace
        root = self.reconciler.render(Flex(
            item("B", "b", 36),
            width=160, height=80,
        ))
        widget = root.children[0].handle.widget
        native_scaling = float(self.host.tk.call("tk", "scaling"))
        pixel_space = DevicePixelSpace.from_widget("tk", self.host)
        self.assertGreater(native_scaling, 0)
        self.assertEqual(pixel_space.scale, 1.0)
        self.assertEqual(rect(widget), (0, 0, 36, 20))
        self.assertLessEqual(self.renderer._sfle_physical_commit_error, 1.0)

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

    def test_image_intrinsic_source_resize_and_keyed_native_reuse(self):
        from psx import Image
        with TemporaryDirectory() as directory:
            source = str(Path(directory) / "native.png")
            write_png(source, 24, 12)
            root = self.reconciler.render(Flex(
                Image(source, key="img", fit="contain"),
                item("Below", "below", 30),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            img, button = [child.handle.widget for child in root.children]
            self.assertIsInstance(img, ttk.Label)
            self.assertEqual(rect(img), (0, 0, 24, 12))
            self.assertEqual(rect(button)[1], 12)
            self.assertIs(img.master, root.handle.widget)
            self.assertEqual(img.winfo_manager(), "place")
            self.assertIsNotNone(img._psx_photo)
            self.assertIsNone(self.renderer._sfle_resize_error)
            updated = self.reconciler.render(Flex(
                Image(source, key="img", fit="cover",
                      layout_width="60px", layout_height="30px"),
                item("Below", "below", 30),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            self.assertIs(updated.children[0].handle.widget, img)
            self.assertEqual(rect(img), (0, 0, 60, 30))
            self.assertEqual(rect(button)[1], 30)
            self.assertGreater(img._psx_photo.width(), 0)
            self.assertEqual((img._psx_photo.width(), img._psx_photo.height()), (60, 30))
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_image_invalid_source_requires_actual_native_intrinsic_measurement(self):
        from psx import Image
        with self.assertRaisesRegex(SFLEError, "intrinsic dimensions"):
            self.reconciler.render(Flex(
                Image("this-source-does-not-exist.png"), width=160, height=80,
            ))

    def test_portable_link_badge_divider_spacer_are_sfle_owned(self):
        from psx import Link, Badge, Divider, Spacer

        def declaration(label, thickness):
            return Flex(
                Link(label="Guide", key="link", layout_width="72px",
                     layout_height="24px", flex_basis="72px", flex_shrink=0),
                Badge(label=label, key="badge", layout_width="78px",
                      layout_height="24px", flex_basis="78px", flex_shrink=0),
                Divider(thickness=thickness, key="divider",
                        layout_width="34px", layout_height=f"{thickness}px",
                        flex_basis="34px", flex_shrink=0),
                Spacer(key="spacer", flex_grow=1, flex_basis="0px",
                       layout_height="10px"),
                item("End", "end", 30),
                direction="row", gap=6, width="340px", height="80px",
                align_items="flex-start",
            )
        self.renderer.set_sfle_constraints(constraints(340, 80))
        root = self.reconciler.render(declaration("READY", 3))
        widgets = [child.handle.widget for child in root.children]
        link, badge, divider, spacer, end = widgets
        self.assertIsInstance(link, tk.Label)
        self.assertIsInstance(badge, tk.Canvas)
        self.assertIsInstance(divider, tk.Canvas)
        self.assertIsInstance(spacer, ttk.Frame)
        self.assertEqual([rect(w) for w in widgets], [
            (0, 0, 72, 24), (78, 0, 78, 24), (162, 0, 34, 3),
            (202, 0, 102, 10), (310, 0, 30, 20),
        ])
        self.assertTrue(all(w.winfo_manager() == "place" for w in widgets))
        self.assertTrue(all(w.master is root.handle.widget for w in widgets))
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

        updated = self.reconciler.render(declaration("DONE", 5))
        self.assertTrue(all(updated.children[i].handle.widget is w
                            for i, w in enumerate(widgets)))
        self.assertEqual(rect(divider), (162, 0, 34, 5))
        self.assertEqual(rect(spacer), (202, 0, 102, 10))
        self.assertEqual(badge._psx_badge_font.metrics("linespace") > 0, True)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_switch_spinbox_select_sfle_geometry_and_state_preservation(self):
        from psx import Switch, SpinBox, Select
        calls = []

        def view(tag, checked=False, value=2, selected="a"):
            return Flex(
                Switch(
                    key="sw", checked=checked, label="Network",
                    on_change=lambda v: calls.append(("switch", tag, v)),
                    layout_width="80px", layout_height="32px",
                    flex_basis="80px", flex_shrink=0,
                ),
                SpinBox(
                    key="spin", value=value, min=0, max=9,
                    on_change=lambda v: calls.append(("spin", tag, v)),
                    layout_width="130px", layout_height="36px",
                    flex_basis="130px", flex_shrink=0,
                ),
                Select(
                    key="select", options=(
                        {"label": "Alpha", "value": "a"},
                        {"label": "Beta", "value": "b"},
                    ), value=selected,
                    on_change=lambda v: calls.append(("select", tag, v)),
                    layout_width="110px", layout_height="34px",
                    flex_basis="110px", flex_shrink=0,
                ),
                width="380px", height="80px", gap=6,
                align_items="flex-start",
            )

        self.renderer.set_sfle_constraints(constraints(380, 80))
        root = self.reconciler.render(view("before"))
        sw, spin, select = widgets = [item.handle.widget for item in root.children]
        self.assertIsInstance(sw, ttk.Frame)
        self.assertIsInstance(spin, ttk.Frame)
        self.assertIsInstance(select, ttk.Combobox)
        self.assertEqual([rect(w) for w in widgets], [
            (0, 0, 80, 32), (86, 0, 130, 36), (222, 0, 110, 34),
        ])
        self.assertTrue(all(w.winfo_manager() == "place" for w in widgets))
        self.assertTrue(all(w.master is root.handle.widget for w in widgets))
        sw._psx_canvas.event_generate("<ButtonRelease-1>")
        spin._psx_parts[2].invoke()
        select.current(1)
        select.event_generate("<<ComboboxSelected>>")
        self.assertEqual(calls, [
            ("switch", "before", True),
            ("spin", "before", 3),
            ("select", "before", "b"),
        ])

        updated = self.reconciler.render(view("after", True, 3, "b"))
        self.assertTrue(all(updated.children[i].handle.widget is w
                            for i, w in enumerate(widgets)))
        self.assertEqual(spin._psx_var.get(), "3")
        self.assertEqual(select.get(), "Beta")
        self.assertEqual(len(calls), 3)
        sw._psx_canvas.event_generate("<ButtonRelease-1>")
        spin._psx_parts[2].invoke()
        select.current(0)
        select.event_generate("<<ComboboxSelected>>")
        self.assertEqual(calls[3:], [
            ("switch", "after", False),
            ("spin", "after", 4),
            ("select", "after", "a"),
        ])
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_structural_box_radiogroup_and_labeled_divider_native_rectangles(self):
        from psx import Radio, RadioGroup, Divider
        from psx.core.vnode import Box
        events = []
        self.renderer.set_sfle_constraints(constraints(340, 300))
        root = self.reconciler.render(Flex(
            Box(Flex(
                item("Nested", "nested", 40),
                width="100%", height="100%", align_items="flex-start",
            ), key="box"),
            RadioGroup(
                Radio("a", label="Alpha", key="a",
                      layout_width="70px", layout_height="24px",
                      flex_basis="24px", flex_shrink=0),
                Radio("b", label="Beta", key="b",
                      layout_width="70px", layout_height="24px",
                      flex_basis="24px", flex_shrink=0),
                key="group", value="a", spacing=4, padding=3,
                layout_width="140px", layout_height="70px",
                on_change=events.append,
            ),
            Divider(
                Text("Section", key="label", layout_width="65px",
                     layout_height="20px", flex_basis="65px", flex_shrink=0),
                key="divider", layout_width="140px", layout_height="30px",
            ),
            direction="column", width="340px", height="300px",
            align_items="flex-start",
        ))
        box, group, divider = (c.handle.widget for c in root.children)
        inner = root.children[0].children[0].handle.widget
        radio_a, radio_b = (c.handle.widget for c in root.children[1].children)
        label = root.children[2].children[0].handle.widget
        self.assertIs(inner.master, box)
        self.assertIs(radio_a.master, group)
        self.assertIs(radio_b.master, group)
        self.assertIs(label.master, divider)
        self.assertEqual(inner.winfo_manager(), "place")
        self.assertEqual(radio_a.winfo_manager(), "place")
        self.assertEqual(label.winfo_manager(), "place")
        self.assertIsNone(divider._psx_child_window_id)
        self.assertGreater(rect(label)[2], 0)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)
        radio_b.invoke()
        self.assertEqual(events, ["b"])

    def test_scroll_basic_sfle_viewport_and_explicit_flex_content(self):
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 100))
        root = self.reconciler.render(Flex(
            Scroll(
                Flex(item("Inside", "inside", 40),
                     direction="row", width="100%", height="100%",
                     align_items="flex-start", key="content"),
                direction="vertical", width=120, height=80,
                key="scroll", layout_width="120px", layout_height="80px",
                flex_basis="120px", flex_shrink=0,
            ),
            direction="row", width="300px", height="100px",
            align_items="flex-start",
        ))
        scroll = root.children[0].handle.widget
        content = root.children[0].children[0].handle.widget
        child = root.children[0].children[0].children[0].handle.widget
        self.assertIs(content.master, scroll._psx_content)
        self.assertIs(child.master, content)
        self.assertEqual(scroll.winfo_manager(), "place")
        self.assertEqual(content.winfo_manager(), "place")
        self.assertEqual(rect(scroll), (0, 0, 120, 80))
        self.assertEqual(rect(content), (0, 0, 120, 80))
        self.assertEqual(rect(child), (0, 0, 40, 20))
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_unported_builtin_is_explicit_failure_not_native_layout_fallback(self):
        from psx import Row
        with self.assertRaisesRegex(RendererCapabilityError, "not certified"):
            self.reconciler.render(Flex(Row(), width=160, height=80))

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

    def test_input_placeholder_overlay_is_not_user_value_and_hides_on_update(self):
        from psx import Input
        def view(value, hint):
            return Flex(
                Input(value=value, placeholder=hint, key="input",
                      layout_width="180px", layout_height="32px",
                      flex_basis="180px", flex_shrink=0),
                direction="row", width="160px", height="80px",
                align_items="flex-start",
            )
        root = self.reconciler.render(view("", "Name"))
        entry = root.children[0].handle.widget
        self.assertEqual(entry.get(), "")
        self.assertEqual(entry._psx_hint_label.cget("text"), "Name")
        self.assertEqual(entry._psx_hint_label.winfo_manager(), "place")
        updated = self.reconciler.render(view("Alice", "Your name"))
        self.assertIs(updated.children[0].handle.widget, entry)
        self.assertEqual(entry.get(), "Alice")
        self.assertEqual(entry._psx_hint_label.winfo_manager(), "")
        self.reconciler.render(view("", "Your name"))
        self.assertEqual(entry._psx_hint_label.cget("text"), "Your name")
        self.assertEqual(entry._psx_hint_label.winfo_manager(), "place")

    def test_input_native_geometry_comes_from_sfle_and_reuses_entry(self):
        from psx import Input
        root = self.reconciler.render(Flex(
            Input(
                value="Alpha", key="input", layout_width="120px",
                layout_height="25px", flex_basis="120px", flex_shrink=0,
            ),
            direction="row", width="160px", height="80px",
            align_items="flex-start",
        ))
        entry = root.children[0].handle.widget
        self.assertIsInstance(entry, (ttk.Entry, tk.Entry))
        self.assertEqual(rect(entry), (0, 0, 120, 25))
        self.assertEqual(entry.winfo_manager(), "place")
        self.assertIs(entry.master, root.handle.widget)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)
        updated = self.reconciler.render(Flex(
            Input(
                value="Beta", key="input", layout_width="90px",
                layout_height="25px", flex_basis="90px", flex_shrink=0,
            ),
            direction="row", width="160px", height="80px",
            align_items="flex-start",
        ))
        self.assertIs(updated.children[0].handle.widget, entry)
        self.assertEqual(rect(entry), (0, 0, 90, 25))
        self.assertEqual(entry.get(), "Beta")

    def test_progressbar_native_sfle_geometry_without_pack(self):
        from psx import ProgressBar
        root = self.reconciler.render(Flex(
            ProgressBar(
                value=45, min=0, max=100, key="progress",
                layout_width="110px", layout_height="22px",
                flex_basis="110px", flex_shrink=0,
            ),
            direction="row", width="160px", height="80px",
            align_items="flex-start",
        ))
        widget = root.children[0].handle.widget
        self.assertIsInstance(widget, ttk.Progressbar)
        self.assertEqual(rect(widget), (0, 0, 110, 22))
        self.assertEqual(widget.winfo_manager(), "place")
        self.assertEqual(widget.master, root.handle.widget)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)
        updated = self.reconciler.render(Flex(
            ProgressBar(
                value=80, min=0, max=100, key="progress",
                layout_width="125px", layout_height="22px",
                flex_basis="125px", flex_shrink=0,
            ),
            direction="row", width="160px", height="80px",
            align_items="flex-start",
        ))
        self.assertIs(updated.children[0].handle.widget, widget)
        self.assertEqual(rect(widget), (0, 0, 125, 22))
        self.assertEqual(round(float(widget["value"])), 80)

    def test_default_tk_renderer_preserves_g1_fail_closed_route(self):
        regular = TkinterRenderer(root=self.host)
        try:
            with self.assertRaisesRegex(RendererCapabilityError, "F3-G2 SFLE geometry"):
                Reconciler(regular).render(Flex(width=160, height=80))
        finally:
            regular.close()

    def test_button_native_lifecycle_is_observed_through_reconciliation(self):
        from psx.sfle.f3_g2_oracles import Observation, ORACLES

        calls = []
        original = lambda: calls.append("old")
        replacement = lambda: calls.append("new")
        first = self.reconciler.render(Flex(
            Button("Old", key="action", on_click=original,
                   layout_width="40px", layout_height="20px"),
            item("Peer", "peer", 20),
            width=160, height=80, gap=4, align_items="flex-start",
        ))
        widget = first.children[0].handle.widget

        def observe(*, mounted=True, disposed=False, state=None, order=(),
                    callback=None, events=()):
            return Observation(
                native_identity=id(widget), mounted=mounted, rect=rect(widget)
                if mounted else None, state=state, order=order,
                callback_identity=callback, events=events, disposed=disposed,
            )

        created = observe(state=widget.cget("text"))
        ORACLES["create"](None, created)
        widget.invoke()
        self.assertEqual(calls, ["old"])

        after = self.reconciler.render(Flex(
            item("Peer", "peer", 20),
            Button("New", key="action", on_click=replacement,
                   layout_width="40px", layout_height="20px"),
            width=160, height=80, gap=4, align_items="flex-start",
        ))
        self.assertIs(after.children[1].handle.widget, widget)
        ORACLES["update"](created, observe(state=widget.cget("text")))
        self.assertEqual(widget.cget("text"), "New")
        self.assertLess(rect(after.children[0].handle.widget)[0], rect(widget)[0])
        ORACLES["reorder"](
            observe(order=("action", "peer")),
            observe(order=("peer", "action")),
        )
        widget.invoke()
        self.assertEqual(calls, ["old", "new"])
        ORACLES["event_rebind"](
            observe(callback=id(original)),
            observe(callback=id(replacement), events=(id(replacement),)),
        )
        before_unmount = observe()
        self.reconciler.unmount()
        self.assertFalse(widget.winfo_exists())
        ORACLES["unmount"](
            before_unmount, observe(mounted=False, disposed=True),
        )

    def test_registered_builtin_lifecycle_keeps_real_native_identity(self):
        """Exercise every native built-in family, not only Button."""
        from psx import (Text, Button, Input, Checkbox, TextArea, Slider,
                         Spacer, Divider, Image, ProgressBar, Radio,
                         RadioGroup, Select, Switch, Link, Badge, SpinBox,
                         Scroll)
        from psx.core.vnode import Box
        from psx.core.vnode import create_element
        from psx.sfle.f3_g2_oracles import Observation, ORACLES
        from psx.sfle.f3_native_coverage import G2_LEAF_TYPES
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import base64

        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "pixel.png"
            write_png(image_path, 2, 2)

            factories = {
                "Text": lambda: Text("Before"),
                "Button": lambda: Button("Before"),
                "Input": lambda: Input(value="Before"),
                "Checkbox": lambda: Checkbox(checked=False),
                "TextArea": lambda: TextArea("Before"),
                "Slider": lambda: Slider(value=30),
                "Spacer": lambda: Spacer(),
                "Divider": lambda: Divider(),
                "Image": lambda: Image(str(image_path)),
                "ProgressBar": lambda: ProgressBar(value=30),
                "Radio": lambda: Radio("a", label="Before"),
                "RadioGroup": lambda: RadioGroup(Radio("a", label="Before")),
                "Select": lambda: Select(options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}], value="a"),
                "Switch": lambda: Switch(checked=False),
                "Link": lambda: Link(label="Before"),
                "Badge": lambda: Badge(label="Before"),
                "SpinBox": lambda: SpinBox(value=30),
                "Scroll": lambda: Scroll(
                    Flex(Text("Content", layout_width="30px",
                              layout_height="15px"), width="40px", height="24px")
                ),
                "Box": lambda: Box(Text("Inside", layout_width="30px",
                                       layout_height="15px")),
                "Flex": lambda: Flex(Text("Inside", layout_width="30px",
                                         layout_height="15px")),
            }
            native = set(G2_LEAF_TYPES["tk"]) | {"Flex"}
            self.assertEqual(set(factories), native)

            def built(name, width):
                if name == "Box":
                    return create_element(
                        "Box", Text("Inside", layout_width=f"{width}px",
                                    layout_height="15px"), key="item",
                    )
                base = factories[name]()
                props = {**dict(base.props), "flex_basis": f"{width}px",
                         "flex_shrink": 0}
                if name == "Flex":
                    props.update(width=f"{width}px", height="24px")
                else:
                    props.update(layout_width=f"{width}px",
                                 layout_height="24px")
                return create_element(base.type, *base.children,
                                      key="item", **props)

            def view(name, width, reverse=False):
                target = built(name, width)
                peer = item("Peer", "peer", 20)
                return Flex(*( (peer, target) if reverse else (target, peer) ),
                            width=160, height=80, gap=8,
                            align_items="flex-start")

            for name in sorted(native):
                with self.subTest(component=name):
                    self.reconciler.unmount()
                    root = self.reconciler.render(view(name, 60))
                    instance = root.children[0]
                    handle = instance.handle
                    widget = handle.widget
                    before = rect(widget)
                    self.assertEqual(before[2], 60, name) if name != "Box" else self.assertGreater(before[2], 0, name)
                    self.assertEqual(before[3], 24, name) if name != "Box" else self.assertGreater(before[3], 0, name)
                    previous_order = tuple(child.node.key for child in root.children)
                    previous_state = (
                        before,
                        tuple(dict(child.node.props) for child in instance.children),
                    )
                    before_observation = Observation(
                        native_identity=id(widget), mounted=True, rect=before,
                        state=previous_state, order=previous_order,
                    )
                    ORACLES["create"](None, before_observation)
                    updated = self.reconciler.render(view(name, 80, reverse=True))
                    current = updated.children[1]
                    self.assertIs(current, instance, name)
                    self.assertIs(current.handle, handle, name)
                    self.assertIs(current.handle.widget, widget, name)
                    after = rect(widget)
                    self.assertEqual(after[2], 80, name) if name != "Box" else self.assertGreater(after[2], 0, name)
                    self.assertGreater(after[0], 0, name)
                    self.assertLess(rect(updated.children[0].handle.widget)[0],
                                    after[0], name)
                    current_state = (
                        after,
                        tuple(dict(child.node.props) for child in instance.children),
                    )
                    after_observation = Observation(
                        native_identity=id(widget), mounted=True, rect=after,
                        state=current_state,
                        order=tuple(child.node.key for child in updated.children),
                    )
                    ORACLES["update"](before_observation, after_observation)
                    ORACLES["reorder"](before_observation, after_observation)
                    # Invalid callback changes must fail before touching the
                    # actual native widget or its last committed rectangle.
                    attempted = view(name, 80, reverse=True)
                    original = attempted.children[1]
                    from dataclasses import replace
                    from types import MappingProxyType
                    invalid = replace(
                        original, props=MappingProxyType({
                            **dict(original.props), "on_invalid": 1,
                        }),
                    )
                    forged = replace(
                        attempted, children=(attempted.children[0], invalid),
                    )
                    with self.assertRaises((TypeError, RendererCapabilityError)):
                        self.reconciler.render(forged)
                    self.assertIs(updated.children[1].handle.widget, widget, name)
                    self.assertEqual(rect(widget), after, name)
                    ORACLES["rollback"](
                        after_observation, Observation(
                            native_identity=id(widget), mounted=True,
                            rect=after, state=current_state,
                            order=after_observation.order, mutation_failed=True,
                        ),
                    )
                    self.reconciler.render(Flex(
                        item("Peer", "peer", 20), width=160, height=80,
                        align_items="flex-start",
                    ))
                    self.assertTrue(instance.disposed, name)
                    self.assertFalse(widget.winfo_exists(), name)
                    ORACLES["unmount"](
                        after_observation, Observation(
                            native_identity=id(widget), mounted=False,
                            rect=after, state=current_state, disposed=True,
                        ),
                    )
            self.reconciler.unmount()


    def test_all_callback_controls_keep_one_live_slot_after_reconciliation(self):
        """Exercise per-control callback replacement against real mounted widgets."""
        from psx import (Button, Input, TextArea, Checkbox, Slider, RadioGroup,
                         Radio, Select, Switch, Link, SpinBox)
        from psx.core.vnode import create_element
        from psx.sfle.f3_g2_contracts import EVENTLESS

        factories = {
            "Button": (Button("Action"), "on_click", ()),
            "Input": (Input(value="a"), "on_change", ("new",)),
            "TextArea": (TextArea("a"), "on_change", ("new",)),
            "Checkbox": (Checkbox(), "on_change", (True,)),
            "Slider": (Slider(value=2), "on_change", (3.0,)),
            "RadioGroup": (RadioGroup(Radio("a")), "on_change", ("a",)),
            "Select": (Select(options=(
                {"label": "A", "value": "a"},
                {"label": "B", "value": "b"}), value="a"), "on_change", ("b",)),
            "Switch": (Switch(), "on_change", (True,)),
            "Link": (Link(label="Action"), "on_click", ()),
            "SpinBox": (SpinBox(value=2), "on_change", (3,)),
        }
        from psx.sfle.f3_native_coverage import G2_LEAF_TYPES
        native = set(G2_LEAF_TYPES["tk"]) | {"Flex"}
        self.assertEqual(set(factories), native - set(EVENTLESS))
        for name, (base, event, args) in factories.items():
            with self.subTest(component=name):
                calls = []
                self.reconciler.unmount()
                def view(callback):
                    target = create_element(
                        base.type, *base.children, key="case",
                        **{**dict(base.props), event: callback,
                           "layout_width": "70px", "layout_height": "28px",
                           "flex_basis": "70px", "flex_shrink": 0},
                    )
                    return Flex(target, width=160, height=80,
                                align_items="flex-start")
                initial = self.reconciler.render(
                    view(lambda *values: calls.append(("old", values))))
                instance = initial.children[0]
                native_handle = instance.handle.widget
                slot = instance.event_slots[event][0]
                slot.invoke(*args)
                self.assertEqual(calls, [("old", args)], name)
                updated = self.reconciler.render(
                    view(lambda *values: calls.append(("new", values))))
                self.assertIs(updated.children[0], instance)
                self.assertIs(instance.handle.widget, native_handle)
                self.assertIs(instance.event_slots[event][0], slot)
                self.assertEqual(len(instance.event_slots), 1, name)
                slot.invoke(*args)
                self.assertEqual(calls, [("old", args), ("new", args)], name)
                self.reconciler.unmount()
                slot.invoke(*args)
                self.assertEqual(len(calls), 2, name)

