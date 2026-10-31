"""G2 native Tkinter SFLE: real ttk geometry and no pack/grid fallbacks."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import struct
from types import SimpleNamespace
import zlib
import tkinter as tk
from tkinter import ttk
import unittest
import sys

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

    def test_nested_grid_uses_one_rollback_snapshot_per_tk_transaction(self):
        from unittest.mock import patch
        from psx.sfle.mixed_grid_native import MountedMixedGrid

        root = self.reconciler.render(psx(
            '<div><Grid gap="8px"><GridItem span="6">'
            '<div>Native card</div></GridItem></Grid></div>'
        ))
        original = MountedMixedGrid.snapshot
        calls = []

        def tracked(grid):
            calls.append(grid)
            return original(grid)

        with patch.object(MountedMixedGrid, "snapshot", tracked):
            self.renderer.set_sfle_constraints(constraints(240, 80))
            self.renderer.commit_layout(root)
        self.assertEqual(len(calls), 1)


    def test_stable_tk_viewport_resize_reuses_settled_native_measurement_baseline(self):
        from unittest.mock import patch

        root = self.reconciler.render(Flex(
            Text("Stable native text", key="text"), width="100%", height="100%",
        ))
        with patch.object(
            self.renderer.root, "update_idletasks",
            wraps=self.renderer.root.update_idletasks,
        ) as idle:
            self.renderer.set_sfle_constraints(constraints(220, 80))
            self.renderer.commit_layout(root)
            # Only the post-placement drain remains. The prior successful
            # transaction already settled native requested-size hints.
            self.assertEqual(idle.call_count, 1)
            idle.reset_mock()
            self.renderer._sfle_measurement_invalidations.request("font")
            self.renderer.commit_layout(root)
            self.assertGreaterEqual(idle.call_count, 2)
            self.renderer._sfle_measurement_invalidations.acknowledge(
                self.renderer._sfle_measurement_invalidations.epoch,
            )


    def test_aqua_surface_sync_skips_only_unchanged_geometry_resizes(self):
        from unittest.mock import patch

        root = self.reconciler.render(Flex(
            Text("Constant", key="text"), width="100%", height="100%",
        ))
        self.assertIsNotNone(self.renderer._sfle_committed_signatures)
        with patch.object(self.renderer, "_sync_aqua_layout_surfaces") as sync:
            self.renderer.set_sfle_constraints(constraints(240, 80))
            self.renderer.commit_layout(root)
            sync.assert_not_called()
            # Theme changes can change native background even without any
            # declarative property edits: force the original full walk.
            self.renderer._sfle_measurement_invalidations.request("theme")
            self.renderer.commit_layout(root)
            sync.assert_called_once()
            self.renderer._sfle_measurement_invalidations.acknowledge(
                self.renderer._sfle_measurement_invalidations.epoch,
            )


    def test_centered_column_block_and_text_widths_survive_resize(self):
        self.renderer.set_sfle_constraints(constraints(500, 500))
        root = self.reconciler.render(psx(
            '<div style="display: flex; flex-direction: column; '
            'align-items: center; gap: 16px; height: 100vh">'
            '<h1>Get started</h1>'
            '<p style="background-color: red">Edit src/App.tsx and save to test HMR</p>'
            '<button>Count is 0</button></div>'
        ))
        title, paragraph, button = root.children
        for viewport in (500, 280, 160, 500):
            self.renderer.set_sfle_constraints(constraints(viewport, 500))
            self.renderer.commit_layout(root)
            for block in (title, paragraph):
                actual = rect(block.handle.widget)
                self.assertAlmostEqual(actual[2], viewport, delta=1)
                label = block.children[0].handle.widget
                label_size = rect(label)
                self.assertGreaterEqual(actual[3], label_size[3] - 1)
                self.assertAlmostEqual(label_size[2], viewport, delta=1)
            self.assertLess(rect(button.handle.widget)[2], viewport)
            self.assertGreaterEqual(
                rect(button.handle.widget)[1],
                rect(paragraph.handle.widget)[1] + rect(paragraph.handle.widget)[3],
            )
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_inline_span_stays_on_paragraph_line_in_tk(self):
        self.renderer.set_sfle_constraints(constraints(800, 400))
        root = self.reconciler.render(psx(
            '<div style="display:flex; flex-direction:column; '
            'align-items:center; height:100vh">'
            '<p>Edit <span style="color:red">src/App.tsx</span>'
            ' and save to test HMR</p>'
            '<button>Count is 0</button></div>'
        ))
        paragraph, button = root.children
        prefix = paragraph.children[0].handle.widget
        span = paragraph.children[1].handle.widget
        suffix = paragraph.children[2].handle.widget
        nested = paragraph.children[1].children[0].handle.widget
        assert rect(prefix)[1] == rect(span)[1] == rect(suffix)[1]
        assert rect(prefix)[0] < rect(span)[0] < rect(suffix)[0]
        assert nested.cget("text") == "src/App.tsx"
        assert rect(paragraph.handle.widget)[2] == 800
        assert rect(button.handle.widget)[1] >= (
            rect(paragraph.handle.widget)[1] + rect(paragraph.handle.widget)[3]
        )
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)
        for width in (220, 800):
            self.renderer.set_sfle_constraints(constraints(width, 400))
            self.renderer.commit_layout(root)
            assert abs(rect(paragraph.handle.widget)[2] - width) <= 1
            assert rect(paragraph.handle.widget)[3] >= rect(prefix)[3]
            assert rect(button.handle.widget)[1] >= (
                rect(paragraph.handle.widget)[1] + rect(paragraph.handle.widget)[3]
            )
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_css_background_is_scoped_to_a_single_ttk_frame(self):
        first = self.reconciler.render(psx('<div key="same" style="background-color: #112233" />'))
        widget = first.handle.widget
        style_name = widget.cget("style")
        self.assertEqual(ttk.Style(widget).lookup(style_name, "background"), "#112233")
        changed = self.reconciler.render(psx('<div key="same" style="background-color: #aabbcc" />'))
        self.assertIs(changed.handle.widget, widget)
        self.assertEqual(ttk.Style(widget).lookup(style_name, "background"), "#aabbcc")
        self.reconciler.render(psx('<div key="same" />'))
        self.assertEqual(widget.cget("style"), "TFrame")

    def test_css_fill_is_stacked_over_native_theme_below_content(self):
        root = self.reconciler.render(psx(
            '<div style="background: #f5f6f8">'
            '<p>Visible text</p></div>'
        ))
        widget = root.handle.widget
        surface = widget._psx_css_fill_canvas
        children = list(widget.winfo_children())
        self.assertIn(surface, children)
        self.assertEqual(children[0], surface)
        self.assertEqual(str(surface.cget("background")), "#f5f6f8")
        self.assertTrue(any(isinstance(child, ttk.Frame) for child in children[1:]))

    def test_css_text_uses_nearest_explicit_ancestor_background(self):
        root = self.reconciler.render(psx(
            '<div style="background: #f5f6f8">'
            '<div style="background: #ffffff">'
            '<p key="copy" style="color: #333333">Text</p>'
            '</div></div>'
        ))
        paragraph = root.children[0].children[0]
        def text_widget(instance):
            if isinstance(getattr(getattr(instance, "handle", None), "widget", None), (tk.Label, ttk.Label)):
                return instance.handle.widget
            for child in instance.children:
                found = text_widget(child)
                if found is not None:
                    return found
            return None
        label = text_widget(paragraph)
        self.assertIsNotNone(label)
        self.assertEqual(
            str(label.cget("background")) if isinstance(label, tk.Label) else
            ttk.Style(label).lookup(label.cget("style"), "background"),
            "#ffffff",
        )
        if isinstance(label, ttk.Label):
            self.assertEqual(
                ttk.Style(label).lookup(label.cget("style"), "foreground"),
                ttk.Style(label).lookup("TLabel", "foreground"),
            )
        updated = self.reconciler.render(psx(
            '<div style="background: #f5f6f8">'
            '<div style="background: #ddeeff">'
            '<p key="copy" style="color: #333333">Text</p>'
            '</div></div>'
        ))
        self.assertIs(text_widget(updated.children[0].children[0]), label)
        self.assertEqual(
            str(label.cget("background")) if isinstance(label, tk.Label) else
            ttk.Style(label).lookup(label.cget("style"), "background"),
            "#ddeeff",
        )

    def test_css_bottom_border_only_paints_declared_edge(self):
        root = self.reconciler.render(psx(
            '<div style="background: #ffffff">'
            '<p key="item" style="border-bottom: 1px solid #e0e0e0">Row</p>'
            '</div>'
        ))
        paragraph = root.children[0].handle.widget
        edges = paragraph._psx_css_side_borders
        self.assertEqual(set(edges), {"bottom"})
        self.assertEqual(str(edges["bottom"].cget("background")), "#e0e0e0")
        self.assertEqual(int(edges["bottom"].place_info()["height"]), 1)

    def test_css_width_commits_to_tk_native_geometry(self):
        root = self.reconciler.render(psx(
            '<div>'
            '<button style="width: 45px; height: 15px; margin-left: 3px; padding: 2px; border-width: 1px">Save</button></div>'
        ))
        self.assertEqual(rect(root.children[0].handle.widget)[2:], (51, 21))
        self.assertEqual(rect(root.children[0].handle.widget)[0], 3)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_html_block_places_native_buttons_without_pack_or_grid(self):
        self.renderer.set_sfle_constraints(constraints(240, 140))
        first = self.reconciler.render(psx(
            '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
        ))
        alpha, beta = (child.handle.widget for child in first.children)
        self.assertIsInstance(alpha, tk.Button if sys.platform == "darwin" else ttk.Button)
        self.assertIs(alpha.master, first.handle.widget)
        self.assertEqual(alpha.winfo_manager(), "place")
        self.assertEqual(beta.winfo_manager(), "place")
        first_rect, second_rect = rect(alpha), rect(beta)
        self.assertEqual(first_rect[0], 0)
        self.assertLess(first_rect[2], 240)
        self.assertEqual(second_rect[0], first_rect[2])
        self.assertEqual(second_rect[1], 0)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

        second = self.reconciler.render(psx(
            '<div><button key="b">Beta</button><button key="a">Alpha</button></div>'
        ))
        self.assertIs(second.children[0].handle.widget, beta)
        self.assertIs(second.children[1].handle.widget, alpha)
        self.assertEqual(rect(beta)[1], 0)
        self.assertEqual(rect(alpha)[0], rect(beta)[2])
        self.assertEqual(rect(alpha)[1], 0)

    def test_portable_text_and_activation_event_payloads_from_tk_widgets(self):
        from psx import Input

        old, current = [], []
        self.renderer.set_sfle_constraints(constraints(480, 140))

        def view(tag):
            sink = old if tag == "old" else current
            return Flex(
                Button("Activate", key="button", on_click=lambda: sink.append(("click", None)),
                       layout_width="75px", layout_height="28px"),
                Checkbox(key="check", on_change=lambda value: sink.append(("check", value)),
                         layout_width="35px", layout_height="28px"),
                Input(key="input", value="", on_change=lambda value: sink.append(("input", value)),
                      on_submit=lambda: sink.append(("submit", None)),
                      layout_width="120px", layout_height="28px"),
                TextArea("start", key="textarea",
                         on_change=lambda value: sink.append(
                             ("textarea", value)),
                         layout_width="130px", layout_height="40px"),
                width="480px", height="140px", gap=5, align_items="flex-start",
            )

        root = self.reconciler.render(view("old"))
        widgets = {node.node.key: node.handle.widget for node in root.children}
        old.clear()
        widgets["button"].invoke()
        widgets["check"].invoke()
        widgets["input"].var.set("first")
        widgets["input"].focus_force()
        self.host.update()
        widgets["input"].event_generate("<Return>", when="tail")
        widgets["textarea"].insert("end-1c", "!")
        self.host.update()
        self.assertEqual(old, [
            ("click", None), ("check", True), ("input", "first"),
            ("submit", None), ("textarea", "start!"),
        ])

        updated = self.reconciler.render(view("new"))
        self.assertTrue(all(updated.children[i].handle.widget is widget for i, widget
                            in enumerate(widgets.values())))
        current.clear()
        widgets["button"].invoke()
        widgets["check"].invoke()
        widgets["input"].var.set("second")
        widgets["input"].event_generate("<Return>")
        widgets["textarea"].insert("end-1c", "!")
        self.host.update()
        self.assertEqual(len(old), 5)
        self.assertEqual(current, [
            ("click", None), ("check", False), ("input", "second"),
            ("submit", None), ("textarea", "start!!"),
        ])

    def test_mounted_tk_flex_consumes_canonical_item_lengths(self):
        from unittest.mock import patch

        from psx.sfle.lengths import Length
        from psx.sfle.native_layout_snapshot import PreparedNativeLayoutSnapshot

        original = PreparedNativeLayoutSnapshot.canonical_snapshot
        snapshots = []

        def record_canonical_snapshot(prepared):
            snapshot = original(prepared)
            snapshots.append(snapshot)
            return snapshot

        with patch.object(
            PreparedNativeLayoutSnapshot, "canonical_snapshot",
            record_canonical_snapshot,
        ):
            root = self.reconciler.render(Flex(
                item("Left", "left", 40),
                item("Right", "right", 30),
                direction="row", gap=8, width="160px", height="80px",
            ))

        self.assertTrue(snapshots, "Native Tk must consume canonical item styles.")
        style = dict(snapshots[-1].nodes[1].style)
        self.assertEqual(style["layout_width"], Length.px(40))
        self.assertEqual(style["layout_height"], Length.px(20))
        self.assertEqual(rect(root.children[0].handle.widget), (0, 0, 40, 20))
        self.assertEqual(rect(root.children[1].handle.widget), (48, 0, 30, 20))
        self.assertEqual(root.children[0].handle.widget.winfo_manager(), "place")

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
        self.assertIsInstance(left, tk.Label if sys.platform == 'darwin' else ttk.Label)
        self.assertIsInstance(right, tk.Button if sys.platform == "darwin" else ttk.Button)
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
                  padding="10" align_items="flex-start">
                <Flex direction="row" width="120px" height="40px"
                      gap="6" align_items="flex-start">
                    <Button label="A" key="a" layout_width="30px"
                            layout_height="15px" flex_basis="30px"
                            flex_shrink="0"/>
                    <Button label="B" key="b" layout_width="20px"
                            layout_height="15px" flex_basis="20px"
                            flex_shrink="0"/>
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

    def test_mounted_flex_root_is_not_resized_ahead_of_children(self):
        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
        ))
        frame = root.handle.widget
        original = rect(frame)
        self.renderer.set_sfle_constraints(constraints(240, 120))
        self.assertEqual(rect(frame), original)
        self.renderer.commit_layout(root)
        self.assertEqual(rect(frame), (0, 0, 240, 120))

    def test_root_configure_binding_is_not_inherited_by_resized_children(self):
        """Aqua child Configure storms must never construct root resize Events."""
        mounted = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
        ))
        tag = self.renderer._sfle_resize_bind_tag
        self.assertIsNotNone(tag)
        self.assertEqual(self.host.bindtags().count(tag), 1)
        child = mounted.children[0].handle.widget
        self.assertNotIn(tag, child.bindtags())
        self.assertTrue(self.host.tk.call("bind", tag, "<Configure>"))
        self.renderer.invalidate_layout()
        self.assertNotIn(tag, self.host.bindtags())
        self.assertFalse(self.host.tk.call("bind", tag, "<Configure>"))


    def test_explicit_root_dimensions_ignore_unrelated_host_resize(self):
        from types import SimpleNamespace

        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="160px", height="80px",
            align_items="flex-start",
        ))
        self.host.update_idletasks()
        self.renderer._sfle_on_configure(SimpleNamespace(
            widget=self.host, width=401, height=241,
        ))
        self.assertIsNone(self.renderer._sfle_resize_pending)
        self.assertEqual(
            (self.renderer._sfle_constraints.width.value,
             self.renderer._sfle_constraints.height.value),
            (160, 80),
        )
        self.assertEqual(rect(root.handle.widget), (0, 0, 160, 80))

    def test_html_root_reflows_viewport_lengths_on_native_configure(self):
        from types import SimpleNamespace

        root = self.reconciler.render(psx(
            '<div><button key="action" style="width: 50vw; height: 24px">'
            'Resize</button></div>'
        ))
        button = root.children[0].handle.widget
        self.assertEqual(rect(button)[2], 80)
        # Ignore stale configure notifications and transient Aqua 1x1
        # mapping sizes even when they arrive after a valid layout commit.
        self.renderer._sfle_on_configure(SimpleNamespace(
            widget=self.host, width=1, height=1,
        ))
        self.assertIsNone(self.renderer._sfle_resize_pending)
        self.renderer._sfle_on_configure(SimpleNamespace(
            widget=self.host, width=240, height=120,
        ))
        self.assertIsNone(self.renderer._sfle_resize_pending)
        self.host.geometry("240x120+0+0")
        self.host.update()
        self.host.after(40, self.host.quit)
        self.host.mainloop()
        self.assertIsNone(self.renderer._sfle_resize_error)
        self.assertIs(root.children[0].handle.widget, button)
        self.assertEqual(rect(button)[2], 120)
        self.assertEqual(self.renderer._sfle_constraints.width.value, 240)
        self.host.geometry("400x240+0+0")
        self.host.update()
        self.host.after(40, self.host.quit)
        self.host.mainloop()
        self.assertEqual(self.renderer._sfle_constraints.width.value, 400)
        self.assertEqual(rect(button)[2], 200)

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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)

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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)
        self.renderer.set_sfle_constraints(constraints(160, 500))
        self.renderer.commit_layout(root)
        self.assertEqual(rect(editor)[3], wide_height)
        self.assertEqual(rect(below)[1], wide_height)
        self.assertEqual(editor.get("1.0", "end-1c"), words)
        self.assertEqual(events, [])

        editor.insert("end-1c", " " +
                      " ".join(["additional native text"] * 18))
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

    def test_aqua_live_configure_commits_without_waiting_for_after_callback(self):
        from unittest.mock import patch

        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
        ))
        frame = root.handle.widget
        with patch("psx.renderers.tkinter.tkinter.sys.platform", "darwin"):
            self.host.geometry("260x120+0+0")
            self.host.update()
            self.assertEqual(
                (self.renderer._sfle_constraints.width.value,
                 self.renderer._sfle_constraints.height.value), (260, 120),
            )
            self.assertEqual(rect(frame), (0, 0, 260, 120))
            self.assertIsNone(self.renderer._sfle_resize_pending)
            self.assertIsNone(self.renderer._sfle_resize_after_id)
            self.assertIsNone(self.renderer._sfle_resize_error)

    def test_resize_storm_keeps_latest_dimensions_and_only_one_scheduled_commit(self):
        root = self.reconciler.render(Flex(
            item("A", "a", 30), width="100%", height="100%",
        ))
        child = root.children[0].handle.widget
        try:
            self.host.geometry("210x100+0+0")
            self.host.update()
            scheduled = self.renderer._sfle_resize_after_id
            # A zero-delay callback can complete during update(), rather
            # than remaining queued until a later timer tick.
            if scheduled is None:
                self.assertEqual(self.renderer._sfle_constraints.width.value, 210)
            self.host.geometry("240x110+0+0")
            self.host.update()
            # A timer may fire during a slow Aqua update(); either a
            # still-coalesced request or an already-committed resize is valid.
            if self.renderer._sfle_resize_after_id is not None:
                self.assertEqual(self.renderer._sfle_resize_after_id, scheduled)
                self.assertEqual(self.renderer._sfle_resize_pending, (240, 110))
            else:
                self.assertIsNone(self.renderer._sfle_resize_pending)
                self.assertEqual(
                    (self.renderer._sfle_constraints.width.value,
                     self.renderer._sfle_constraints.height.value), (240, 110))
            # Allow the one coalesced Tcl timer to fire without making
            # assumptions about how fast the host starts a test process.
            self.host.after(30, self.host.quit)
            self.host.mainloop()
            self.assertIsNone(self.renderer._sfle_resize_after_id)
            self.assertIsNone(self.renderer._sfle_resize_error)
            self.assertEqual(
                (self.renderer._sfle_constraints.width.value,
                 self.renderer._sfle_constraints.height.value), (240, 110))
            self.assertIs(root.children[0].handle.widget, child)
        finally:
            self.reconciler.unmount()
            self.host.geometry("400x240+0+0")
            self.host.update()

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
            self.host.after(30, self.host.quit)
            self.host.mainloop()
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
            self.assertLessEqual(
                self.renderer.sfle_result.geometry_commit_error, 1.0)
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
        root = self.reconciler.render(
            Flex(item("A", "a", 30), width=160, height=80))
        widget = root.children[0].handle.widget
        widget.place_forget()
        widget.pack()
        with self.assertRaises(SFLEError) as captured:
            self.renderer.commit_layout(root)
        self.assertEqual(captured.exception.code,
                         DiagnosticCode.UNSUPPORTED_FEATURE)

    def test_engine_generation_mismatch_rejects_without_native_mutation(self):
        root = self.reconciler.render(
            Flex(item("A", "a", 30), width=160, height=80))
        widget = root.children[0].handle.widget
        before = rect(widget)

        class WrongGeneration:
            def compute(self, request):
                valid = PythonLayoutEngine().compute(request)
                return LayoutResult(1, request.generation + 1, valid.boxes)

        self.renderer._sfle_engine = WrongGeneration()
        with self.assertRaises(SFLEError) as captured:
            self.renderer.commit_layout(root)
        self.assertEqual(captured.exception.code,
                         DiagnosticCode.INVALID_SNAPSHOT)
        self.assertEqual(rect(widget), before)

    def test_worker_thread_commit_fails_before_any_tcl_calls(self):
        root = self.reconciler.render(
            Flex(item("A", "a", 30), width=160, height=80))
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
        self.assertEqual(
            errors[0].code, DiagnosticCode.UNSUPPORTED_MEASUREMENT)

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
            self.assertEqual(
                (img._psx_photo.width(), img._psx_photo.height()), (60, 30))
            self.assertLessEqual(
                self.renderer.sfle_result.geometry_commit_error, 1)

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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)

        updated = self.reconciler.render(declaration("DONE", 5))
        self.assertTrue(all(updated.children[i].handle.widget is w
                            for i, w in enumerate(widgets)))
        self.assertEqual(rect(divider), (162, 0, 34, 5))
        self.assertEqual(rect(spacer), (202, 0, 102, 10))
        self.assertEqual(badge._psx_badge_font.metrics("linespace") > 0, True)
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)

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
        sw, spin, select = widgets = [
            item.handle.widget for item in root.children]
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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)

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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)
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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)

    def test_nested_native_tk_wheel_chains_only_remaining_pixels(self):
        from types import SimpleNamespace
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 300))
        root = self.reconciler.render(Flex(
            Scroll(Flex(
                Scroll(Flex(item("Inside", "inside", 40),
                            direction="row", width="300px", height="300px",
                            key="inner-content", align_items="flex-start"),
                       direction="vertical", key="inner",
                       layout_width="120px", layout_height="80px",
                       flex_basis="120px", flex_shrink=0),
                direction="column", width="300px", height="300px",
                key="outer-content", align_items="flex-start"),
                direction="vertical", key="outer",
                layout_width="160px", layout_height="100px",
                flex_basis="160px", flex_shrink=0),
            direction="row", width="300px", height="300px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        inner = root.children[0].children[0].children[0].handle.widget
        self.host.update_idletasks()
        inner._psx_canvas.yview_moveto(1.0)
        outer._psx_canvas.yview_moveto(0)
        self.host.update_idletasks()
        event = SimpleNamespace(
            delta=-6 if sys.platform == "darwin" else -120,
            state=0,
        )
        self.assertIsNone(inner._wheel(event))
        self.assertEqual(outer._wheel(event), "break")
        self.assertLessEqual(abs(outer._psx_canvas.canvasy(0) - 48), 1)
        self.assertEqual(event._psx_scroll_remainder, 0.0)

    def test_scroll_failed_commit_restores_tk_scrollregion_and_offsets(self):
        from unittest.mock import patch
        from psx import Scroll
        from psx.sfle import native_scroll_hosts
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        canvas = outer._psx_canvas
        self.host.update_idletasks()
        canvas.xview_moveto(60 / 300)
        canvas.yview_moveto(30 / 200)
        before_region = canvas.cget("scrollregion")
        original = native_scroll_hosts.apply_tk_scroll

        def fail_after_mutation(host, binding, offset):
            original(host, binding, offset)
            host._psx_canvas.xview_moveto(0)
            host._psx_canvas.yview_moveto(0)
            raise RuntimeError("injected Tk scroll failure")

        with patch.object(native_scroll_hosts, "apply_tk_scroll",
                          side_effect=fail_after_mutation):
            with self.assertRaisesRegex(RuntimeError, "injected Tk"):
                self.renderer.commit_layout(root)
        self.host.update_idletasks()
        self.assertEqual(canvas.cget("scrollregion"), before_region)
        self.assertLessEqual(abs(canvas.canvasx(0) - 60), 1)
        self.assertLessEqual(abs(canvas.canvasy(0) - 30), 1)

    def test_scroll_reflow_keeps_logical_offset_and_native_identity(self):
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        content = root.children[0].children[0].handle.widget
        button = root.children[0].children[0].children[0].handle.widget
        self.host.update_idletasks()
        outer._psx_canvas.xview_moveto(70 / 300)
        outer._psx_canvas.yview_moveto(40 / 200)
        self.host.update_idletasks()
        self.renderer.commit_layout(root)
        self.host.update_idletasks()
        self.assertLessEqual(abs(outer._psx_canvas.canvasx(0) - 70), 1)
        self.assertLessEqual(abs(outer._psx_canvas.canvasy(0) - 40), 1)
        self.assertIs(root.children[0].children[0].handle.widget, content)
        self.assertIs(
            root.children[0].children[0].children[0].handle.widget, button)
        self.assertEqual(content.winfo_manager(), "place")

    def test_scroll_unmount_releases_tk_canvas(self):
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        self.assertTrue(outer.winfo_exists())
        self.reconciler.unmount()
        self.assertTrue(outer._psx_disposed)
        self.assertFalse(outer.winfo_exists())

    def test_scroll_disabled_axes_reset_existing_tk_offsets(self):
        from psx import Scroll
        from psx.sfle.model import Rect
        from psx.sfle.native_scroll_hosts import apply_tk_scroll, binding_from_host
        from psx.sfle.scroll_offsets import ScrollOffset
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        canvas = outer._psx_canvas
        self.host.update_idletasks()
        binding = binding_from_host(outer._psx_props, Rect(0, 0, 120, 80),
                                    Rect(0, 0, 300, 200))
        apply_tk_scroll(outer, binding, ScrollOffset(60, 45))
        self.host.update_idletasks()
        self.assertLessEqual(abs(canvas.canvasy(0) - 45), 1)
        outer._psx_props = {**outer._psx_props, "direction": "horizontal"}
        restricted = binding_from_host(outer._psx_props, Rect(0, 0, 120, 80),
                                       Rect(0, 0, 300, 200))
        apply_tk_scroll(outer, restricted, ScrollOffset(60, 45))
        self.host.update_idletasks()
        self.assertLessEqual(abs(canvas.canvasy(0)), 1)
        self.assertLessEqual(abs(canvas.canvasx(0) - 60), 1)

    def test_native_tk_wheel_and_keyboard_offset_readback(self):
        from types import SimpleNamespace
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="vertical", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        canvas = outer._psx_canvas
        self.host.update_idletasks()
        wheel = SimpleNamespace(
            delta=-6 if sys.platform == "darwin" else -120,
            state=0,
        )
        self.assertEqual(outer._wheel(wheel), "break")
        self.assertLessEqual(abs(canvas.canvasy(0) - 48), 1)
        self.assertEqual(wheel._psx_scroll_remainder, 0)
        self.assertEqual(outer._keyboard(
            SimpleNamespace(keysym="Page_Down")), "break")
        self.assertLessEqual(abs(canvas.canvasy(0) - 120), 1)
        canvas.yview_moveto(1)
        self.host.update_idletasks()
        edge = SimpleNamespace(
            delta=-6 if sys.platform == "darwin" else -120,
            state=0,
        )
        self.assertIsNone(outer._wheel(edge))

    def test_native_scroll_overflow_offsets_and_canvas_clipping(self):
        from psx import Scroll
        from psx.sfle.native_scroll_hosts import apply_tk_scroll, binding_from_host
        from psx.sfle.scroll_offsets import ScrollOffset
        from psx.sfle.model import Rect

        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.reconciler.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        child = root.children[0].children[0].handle.widget
        canvas = outer._psx_canvas
        self.host.update_idletasks()
        self.assertIs(child.master, outer._psx_content)
        self.assertEqual(rect(child), (0, 0, 300, 200))
        self.assertEqual(
            tuple(map(int, canvas.cget("scrollregion").split())), (0, 0, 300, 200))
        binding = binding_from_host(outer._psx_props, Rect(0, 0, 120, 80),
                                    Rect(0, 0, 300, 200))
        result = apply_tk_scroll(outer, binding, ScrollOffset(90, 60))
        self.host.update_idletasks()
        self.assertEqual(result.offset, ScrollOffset(90, 60))
        self.assertLessEqual(abs(canvas.canvasx(0) - 90), 1)
        self.assertLessEqual(abs(canvas.canvasy(0) - 60), 1)
        self.assertEqual(int(canvas.cget("highlightthickness")), 0)
        self.assertEqual(canvas.winfo_width(), 120)
        self.assertEqual(canvas.winfo_height(), 80)

    def test_unported_builtin_is_explicit_failure_not_native_layout_fallback(self):
        from psx.core.registry import builtin_component_registry
        self.assertFalse(builtin_component_registry().contains("Row"))

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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)
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
        self.assertLessEqual(
            self.renderer.sfle_result.geometry_commit_error, 1)
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

    def test_default_tk_renderer_preserves_flex_fail_closed_route(self):
        regular = TkinterRenderer(root=self.host)
        try:
            with self.assertRaisesRegex(RendererCapabilityError, "Native SFLE SFLE geometry"):
                Reconciler(regular).render(Flex(width=160, height=80))
        finally:
            regular.close()

    def test_button_native_lifecycle_is_observed_through_reconciliation(self):
        from psx.sfle.native_operation_oracles import Observation, ORACLES

        calls = []
        def original(): return calls.append("old")
        def replacement(): return calls.append("new")
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
        self.assertLess(rect(after.children[0].handle.widget)[
                        0], rect(widget)[0])
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
        from psx.sfle.native_operation_oracles import Observation, ORACLES
        from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
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
            native = set(NATIVE_LEAF_TYPES["tk"]) | {"Flex"}
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
                return Flex(*((peer, target) if reverse else (target, peer)),
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
                    self.assertEqual(before[2], 60, name) if name != "Box" else self.assertGreater(
                        before[2], 0, name)
                    self.assertEqual(before[3], 24, name) if name != "Box" else self.assertGreater(
                        before[3], 0, name)
                    previous_order = tuple(
                        child.node.key for child in root.children)
                    previous_state = (
                        before,
                        tuple(dict(child.node.props)
                              for child in instance.children),
                    )
                    before_observation = Observation(
                        native_identity=id(widget), mounted=True, rect=before,
                        state=previous_state, order=previous_order,
                    )
                    ORACLES["create"](None, before_observation)
                    updated = self.reconciler.render(
                        view(name, 80, reverse=True))
                    current = updated.children[1]
                    unchanged_peer = updated.children[0].handle.widget
                    self.assertNotIn(id(unchanged_peer),
                                     self.renderer._sfle_native_intrinsic_cache.last_measured,
                                     name)
                    self.assertIs(current, instance, name)
                    self.assertIs(current.handle, handle, name)
                    self.assertIs(current.handle.widget, widget, name)
                    after = rect(widget)
                    self.assertEqual(after[2], 80, name) if name != "Box" else self.assertGreater(
                        after[2], 0, name)
                    self.assertGreater(after[0], 0, name)
                    self.assertLess(rect(updated.children[0].handle.widget)[0],
                                    after[0], name)
                    current_state = (
                        after,
                        tuple(dict(child.node.props)
                              for child in instance.children),
                    )
                    after_observation = Observation(
                        native_identity=id(widget), mounted=True, rect=after,
                        state=current_state,
                        order=tuple(
                            child.node.key for child in updated.children),
                    )
                    ORACLES["update"](before_observation, after_observation)
                    ORACLES["reorder"](before_observation, after_observation)
                    # C5: validate invalidation for every native family.
                    for reason in ("content", "font", "theme", "resource", "dpi", "viewport"):
                        with self.subTest(component=name, reason=reason):
                            previous_generation = self.renderer.sfle_result.generation
                            self.renderer.request_sfle_invalidation(reason)
                            self.renderer.flush()
                            self.assertGreater(self.renderer.sfle_result.generation,
                                               previous_generation, (name, reason))
                            self.assertIs(current.handle.widget,
                                          widget, (name, reason))
                            self.assertFalse(
                                self.renderer._sfle_measurement_invalidations.pending)
                    if name == "Image":
                        import os
                        original_stamp = image_path.stat().st_mtime_ns
                        os.utime(image_path, ns=(
                            original_stamp + 1_000_000_000,
                            original_stamp + 1_000_000_000))
                        prior_resource_generation = self.renderer.sfle_result.generation
                        self.renderer._sfle_poll_image_resources(
                            self.renderer._sfle_invalidation_lifetime)
                        self.renderer.flush()
                        self.assertGreater(self.renderer.sfle_result.generation,
                                           prior_resource_generation, name)
                        self.assertIs(current.handle.widget, widget, name)
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
                    self.assertIs(
                        updated.children[1].handle.widget, widget, name)
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
        from psx.sfle.native_operation_contracts import EVENTLESS

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
        from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
        native = set(NATIVE_LEAF_TYPES["tk"]) | {"Flex"}
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

    def test_semantic_invalidations_preserve_native_tk_widget_identity(self):
        for reason in ("content", "font", "theme", "resource", "dpi", "viewport"):
            with self.subTest(reason=reason):
                self.reconciler.unmount()
                root = self.reconciler.render(Flex(
                    Text("Stable", key="fixed", layout_width="50px",
                         layout_height="20px"),
                    width=160, height=80, align_items="flex-start",
                ))
                widget = root.children[0].handle.widget
                generation = self.renderer.sfle_result.generation
                self.renderer.request_sfle_invalidation(reason)
                self.renderer.request_sfle_invalidation(reason)
                self.renderer.flush()
                self.assertIs(root.children[0].handle.widget, widget)
                self.assertEqual(
                    self.renderer.sfle_result.generation, generation + 1)
                self.assertEqual(
                    self.renderer._sfle_measurement_invalidations.pending, set())
                self.reconciler.unmount()

    def test_tk_theme_changed_event_requests_sfle_remeasurement(self):
        root = self.reconciler.render(Flex(
            Text("Theme", key="label", layout_width="50px",
                 layout_height="20px"),
            width=160, height=80,
        ))
        native = root.children[0].handle.widget
        generation = self.renderer.sfle_result.generation
        self.host.event_generate("<<ThemeChanged>>")
        self.host.update()
        self.renderer.flush()
        self.assertIs(root.children[0].handle.widget, native)
        self.assertGreater(self.renderer.sfle_result.generation, generation)
        self.reconciler.unmount()
        self.assertIsNone(self.renderer._sfle_theme_bind_id)

    def test_readback_race_restores_tk_placement_and_preserves_identity(self):
        from unittest.mock import patch
        import psx.sfle.tkinter_layout_bridge as bridge

        root = self.reconciler.render(Flex(
            item("First", "first", 40), item("Second", "second", 30),
            width=160, height=80, gap=8, align_items="flex-start",
        ))
        widgets = tuple(child.handle.widget for child in root.children)
        before = tuple(rect(widget) for widget in widgets)
        published = self.renderer.sfle_result
        original_error = bridge.DevicePixelSpace.error
        injected = {"done": False}

        def readback_error(space, expected, observed):
            if not injected["done"]:
                injected["done"] = True
                self.renderer._sfle_measurement_invalidations.request(
                    "resource")
            return original_error(space, expected, observed)

        with patch.object(bridge.DevicePixelSpace, "error", readback_error):
            self.renderer.commit_layout(root)
        self.assertTrue(injected["done"],
                        "Native readback assertion must execute")
        self.assertEqual(tuple(rect(widget) for widget in widgets), before)
        self.assertGreaterEqual(
            self.renderer.sfle_result.generation, published.generation + 2)
        self.assertEqual(
            self.renderer._sfle_measurement_invalidations.pending, set())
        self.assertFalse(self.renderer._sfle_measurement_invalidations.pending)
        self.assertTrue(all(child.handle.widget is widget for child,
                        widget in zip(root.children, widgets)))

    def test_native_tk_geometry_application_failure_restores_previous_placement(self):
        from unittest.mock import patch
        import psx.sfle.tkinter_layout_bridge as bridge

        root = self.reconciler.render(Flex(
            item("First", "first", 40), item("Second", "second", 30),
            width=160, height=80, gap=8, align_items="flex-start",
        ))
        widgets = tuple(child.handle.widget for child in root.children)
        before = tuple(rect(widget) for widget in widgets)
        published = self.renderer.sfle_result
        original_committer = bridge.NativeGeometryCommitter

        def interrupted_committer(*args, **kwargs):
            apply = original_committer(*args, **kwargs)

            def fail_after_application(result):
                apply(result)
                widgets[0].place(x=7, y=9, width=13, height=15)
                raise RuntimeError("injected Tk native application failure")
            return fail_after_application

        with patch.object(bridge, "NativeGeometryCommitter", side_effect=interrupted_committer):
            with self.assertRaisesRegex(RuntimeError, "injected Tk native application failure"):
                self.renderer.commit_layout(root)
        self.assertEqual(tuple(rect(widget) for widget in widgets), before)
        self.assertIs(self.renderer.sfle_result, published)
        self.renderer.commit_layout(root)
        self.assertTrue(all(child.handle.widget is widget for child,
                        widget in zip(root.children, widgets)))

    def test_native_tk_geometry_invalidation_during_application_rolls_back(self):
        from unittest.mock import patch
        import psx.sfle.tkinter_layout_bridge as bridge

        root = self.reconciler.render(Flex(
            item("First", "first", 40), item("Second", "second", 30),
            width=160, height=80, gap=8, align_items="flex-start",
        ))
        widgets = tuple(child.handle.widget for child in root.children)
        before = tuple(rect(widget) for widget in widgets)
        published = self.renderer.sfle_result
        original_committer = bridge.NativeGeometryCommitter
        injected = {"done": False}

        def interrupted_committer(*args, **kwargs):
            apply = original_committer(*args, **kwargs)

            def fail_after_application(result):
                apply(result)
                if not injected["done"]:
                    injected["done"] = True
                    self.renderer._sfle_measurement_invalidations.request(
                        "dpi")
            return fail_after_application

        with patch.object(bridge, "NativeGeometryCommitter", side_effect=interrupted_committer):
            self.renderer.commit_layout(root)
        self.assertEqual(tuple(rect(widget) for widget in widgets), before)
        self.assertGreaterEqual(
            self.renderer.sfle_result.generation, published.generation + 2)
        self.assertEqual(
            self.renderer._sfle_measurement_invalidations.pending, set())
        self.assertFalse(self.renderer._sfle_measurement_invalidations.pending)
        self.assertTrue(all(child.handle.widget is widget for child,
                        widget in zip(root.children, widgets)))

    def test_native_local_image_revision_remeasures_without_props_or_remount(self):
        from psx import Image
        with TemporaryDirectory() as directory:
            path = Path(directory) / "revision.png"
            write_png(path, 24, 12)
            root = self.reconciler.render(Flex(
                Image(str(path), key="img", fit="contain"),
                item("Peer", "peer", 30),
                direction="column", width=160, height=80,
                align_items="flex-start",
            ))
            native = root.children[0].handle.widget
            peer = root.children[1].handle.widget
            first_generation = self.renderer.sfle_result.generation
            self.assertEqual(rect(native)[3], 12)
            self.assertEqual(rect(peer)[1], 12)

            write_png(path, 24, 24)
            self.renderer._sfle_poll_image_resources(
                self.renderer._sfle_invalidation_lifetime,
            )
            self.renderer.flush()
            self.assertIs(root.children[0].handle.widget, native)
            self.assertIs(root.children[1].handle.widget, peer)
            self.assertGreater(
                self.renderer.sfle_result.generation, first_generation)
            self.assertEqual(rect(native)[3], 24)
            self.assertEqual(rect(peer)[1], 24)
            self.assertFalse(
                self.renderer._sfle_measurement_invalidations.pending)
            self.assertFalse(
                self.renderer._sfle_image_resource_watch.changed())

    def test_targeted_resource_remeasurement_does_not_measure_unaffected_tk_peer(self):
        root = self.reconciler.render(Flex(
            item("First", "first", 40), item("Second", "second", 30),
            width=160, height=80, gap=8, align_items="flex-start",
        ))
        first, second = (child.handle.widget for child in root.children)
        baseline = tuple(rect(widget) for widget in (first, second))
        self.renderer.request_sfle_invalidation(
            "resource", widget_id=id(first))
        self.renderer.flush()
        cache = self.renderer._sfle_native_intrinsic_cache
        self.assertIn(id(first), cache.last_measured)
        self.assertNotIn(id(second), cache.last_measured)
        self.assertEqual(tuple(rect(widget)
                         for widget in (first, second)), baseline)
        self.assertIs(root.children[0].handle.widget, first)
        self.assertIs(root.children[1].handle.widget, second)


def test_html_flow_public_native_geometry_receipt_tkinter(request):
    from tests.certification.public_behavior_census import Feature, assert_feature
    host = tk.Tk()
    host.geometry("300x180+0+0")
    renderer = TkinterRenderer(
        root=host, sfle_constraints=constraints(220, 120),
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(
            "<div><button>First</button><button>Second</button></div>"
        ))
        first, second = (child.handle.widget for child in root.children)
        a, b = rect(first), rect(second)
        assert_feature(
            request, Feature("div", "tkinter", "interaction", "semantic_flow",
                             "native_geometry", applicability="partial_native"),
            a[0] == 0 and 0 < a[2] < 220
            and 0 < b[2] < 220 and b[0] == a[2] and b[1] == 0
            and first.winfo_manager() == "place",
        )
    finally:
        reconciler.unmount()
        renderer.close()
        host.destroy()


def test_tk_width_measurement_preserves_empty_wraplength_and_skips_unchanged_write():
    """Tcl's empty wraplength is valid and must survive temporary measurements."""
    from psx.sfle.tk_measurement import TkMeasurementSource

    class Widget:
        def __init__(self, wraplength):
            self.wraplength = wraplength
            self.writes = []
            self.flushes = 0

        def keys(self):
            return ("wraplength",)

        def cget(self, name):
            assert name == "wraplength"
            return self.wraplength

        def configure(self, **options):
            self.writes.append(options["wraplength"])
            self.wraplength = options["wraplength"]

        def update_idletasks(self):
            self.flushes += 1

        def winfo_reqwidth(self):
            return 140

        def winfo_reqheight(self):
            return 21

    for initial, expected_writes, expected_flushes in (
        ("", [80, ""], 1),
        (80, [], 1),
        ("80", [], 1),
    ):
        widget = Widget(initial)
        source = TkMeasurementSource({"leaf": widget})
        result = source.measure_width("leaf", 80.0)
        assert result.preferred_width == 80
        assert result.preferred_height == 21
        assert widget.wraplength == initial
        assert widget.writes == expected_writes
        assert widget.flushes == expected_flushes


def test_tk_wrapping_measurements_restore_widget_state_without_extra_idle_drain():
    """Width probes must preserve mounted label wrapping and native hints."""
    from psx.sfle.tk_measurement import TkMeasurementSource
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        label = tk.Label(root, text="Several words that wrap across multiple lines")
        label.configure(wraplength=0)
        source = TkMeasurementSource({"copy": label})
        original = label.cget("wraplength")
        narrow = source.measure_width("copy", 45)
        assert label.cget("wraplength") == original
        wide = source.measure_width("copy", 300)
        assert label.cget("wraplength") == original
        assert narrow.preferred_height >= wide.preferred_height
        # A final idle pass must resolve the restored native option as well.
        root.update_idletasks()
        assert label.cget("wraplength") == original
    finally:
        root.destroy()


def test_tk_grid_transaction_avoids_repeated_idle_drains_for_unchanged_wrap():
    """The Grid bridge drains once; only a changed wrap requires a new drain."""
    from psx.sfle.tk_measurement import TkMeasurementSource

    class Widget:
        def __init__(self, initial=None):
            self.wraplength = initial
            self.flushes = 0
            self.writes = []

        def keys(self):
            return ("wraplength",) if self.wraplength is not None else ()

        def cget(self, name):
            return self.wraplength

        def configure(self, **options):
            self.writes.append(options["wraplength"])
            self.wraplength = options["wraplength"]

        def update_idletasks(self):
            self.flushes += 1

        def winfo_reqwidth(self):
            return 72

        def winfo_reqheight(self):
            return 19

    for previous, width, expected_flushes, writes in (
        (80, 80, 0, []),
        ("80", 80, 0, []),
        (None, 80, 0, []),
        ("", 80, 0, []),
    ):
        widget = Widget(previous)
        source = TkMeasurementSource({"leaf": widget}, idle_synced=True)
        result = source.measure_width("leaf", width)
        assert result.preferred_height == 19
        assert widget.flushes == expected_flushes
        assert widget.writes == writes
        assert widget.wraplength == previous

    unsynced = Widget(80)
    TkMeasurementSource({"leaf": unsynced}).measure_width("leaf", 80)
    assert unsynced.flushes == 1


def test_tk_native_empty_wraplength_is_unwrapped_and_fits_without_probe():
    """An empty Tcl wrap option is unwrapped, not a reason to relayout."""
    import tkinter as tk
    from tkinter import ttk
    from psx.sfle.tk_measurement import TkMeasurementSource

    root = tk.Tk()
    root.withdraw()
    try:
        label = ttk.Label(root, text="Short label")
        label.configure(wraplength="")
        root.update_idletasks()
        before = (label.winfo_reqwidth(), label.winfo_reqheight())
        measured = TkMeasurementSource(
            {"label": label}, idle_synced=True,
        ).measure_width("label", before[0] + 80)
        assert measured.preferred_width == before[0]
        assert measured.preferred_height == before[1]
        assert str(label.cget("wraplength")) == ""
    finally:
        root.destroy()


def test_tk_grid_fit_short_circuits_width_probe_only_for_unwrapped_text():
    """A fitted natural label needs no wrap mutation or Tcl idle drain."""
    from psx.sfle.tk_measurement import TkMeasurementSource

    class Label:
        def __init__(self, natural):
            self.wrap = 0
            self.natural = natural
            self.writes = []
            self.flushes = 0

        def keys(self):
            return ("wraplength",)

        def cget(self, option):
            return self.wrap

        def configure(self, **kwargs):
            self.wrap = kwargs["wraplength"]
            self.writes.append(self.wrap)

        def update_idletasks(self):
            self.flushes += 1

        def winfo_reqwidth(self):
            return self.natural

        def winfo_reqheight(self):
            return 20 if self.wrap == 0 or self.wrap >= self.natural else 40

    fitted = Label(64)
    result = TkMeasurementSource(
        {"text": fitted}, idle_synced=True,
    ).measure_width("text", 100)
    assert (result.preferred_width, result.preferred_height) == (64, 20)
    assert fitted.writes == []
    assert fitted.flushes == 0

    wrapped = Label(140)
    result = TkMeasurementSource(
        {"text": wrapped}, idle_synced=True,
    ).measure_width("text", 100)
    assert (result.preferred_width, result.preferred_height) == (100, 40)
    assert wrapped.writes == [100, 0]
    assert wrapped.flushes == 1

    unsynced = Label(64)
    TkMeasurementSource({"text": unsynced}).measure_width("text", 100)
    assert unsynced.writes == [100, 0]
    assert unsynced.flushes == 1
