"""F3-G2 native Kivy SFLE certification, executed under a real SDL2 provider.

No mock Kivy geometry and no silent skip: xvfb-run must create a window.
The subprocess isolates Kivy's global Clock/Window configuration.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivySFLEGeometrySubprocessTests(unittest.TestCase):
    def test_kivy_intrinsic_controls_without_pixel_bounds(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Flex, Input, Checkbox, ProgressBar
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(450, True), AvailableSize(90, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            def view(value, hint):
                return Flex(
                    Input(value=value, placeholder=hint, key="input"),
                    Checkbox(checked=False, key="checkbox"),
                    ProgressBar(value=55, key="bar"),
                    direction="row", width="450px", height="90px",
                    gap=8, align_items="flex-start",
                )
            root = tree.render(view("", "Account"))
            widgets = [child.handle.widget for child in root.children]
            initial = [tuple(w.size) for w in widgets]
            assert all(0 < w < 400 and 0 < h < 90 for w, h in initial), initial
            assert widgets[0].text == ""
            assert widgets[0].hint_text == "Account"
            assert renderer.sfle_result.geometry_commit_error <= 1
            updated = tree.render(view("A longer account value", "Account"))
            assert [child.handle.widget for child in updated.children] == widgets
            assert widgets[0].text == "A longer account value"
            assert widgets[0].width > initial[0][0], (initial, widgets[0].size)
            assert renderer.sfle_result.geometry_commit_error <= 1
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_kivy_input_explicit_pixel_bounds_preserve_native_widget(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.textinput import TextInput
            from psx import Flex, Input
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            def view(text, width):
                return Flex(
                    Input(
                        value=text, key="input",
                        layout_width=f"{width}px",
                        layout_height="28px",
                        flex_basis=f"{width}px", flex_shrink=0,
                    ),
                    direction="row", width="160px", height="80px",
                    align_items="flex-start",
                )
            root = tree.render(view("Alpha", 120))
            native = root.children[0].handle.widget
            assert isinstance(native, TextInput)
            assert tuple(native.pos) + tuple(native.size) == (0, 52, 120, 28)
            assert renderer.sfle_result.geometry_commit_error <= 1
            root = tree.render(view("Beta", 90))
            assert root.children[0].handle.widget is native
            assert tuple(native.pos) + tuple(native.size) == (0, 52, 90, 28)
            assert native.text == "Beta"
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_explicit_bounds_checkbox_and_progressbar_sfle_geometry(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.checkbox import CheckBox as KivyCheckBox
            from kivy.uix.progressbar import ProgressBar as KivyProgressBar
            from psx import Flex, Checkbox, ProgressBar
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            backend = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True),
                ), engine=PythonLayoutEngine(),
            )
            tree = Reconciler(backend)
            calls = []
            def view(check, progress, width):
                return Flex(
                    Checkbox(
                        checked=check, key="cb", on_change=calls.append,
                        layout_width="24px", layout_height="24px",
                        flex_basis="24px", flex_shrink=0,
                    ),
                    ProgressBar(
                        value=progress, min=0, max=100, key="progress",
                        layout_width=f"{width}px", layout_height="20px",
                        flex_basis=f"{width}px", flex_shrink=0,
                    ),
                    direction="row", gap=8, width="160px", height="80px",
                    align_items="flex-start",
                )
            root = tree.render(view(False, 45, 100))
            cb, bar = (node.handle.widget for node in root.children)
            assert isinstance(cb, KivyCheckBox)
            assert isinstance(bar, KivyProgressBar)
            assert (tuple(cb.pos), tuple(cb.size)) == ((0, 56), (24, 24))
            assert (tuple(bar.pos), tuple(bar.size)) == ((32, 60), (100, 20))
            assert backend.sfle_result.geometry_commit_error <= 1
            assert cb.size_hint == [None, None] or tuple(cb.size_hint) == (None, None)
            cb.active = True
            assert calls == [True], calls
            root = tree.render(view(True, 75, 110))
            assert root.children[0].handle.widget is cb
            assert root.children[1].handle.widget is bar
            assert tuple(bar.size) == (110, 20)
            assert round(bar.value) == 75
            assert len(calls) == 1
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_multiline_text_remeasured_at_real_content_width(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.core.window import Window
            from psx import Flex, Text, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def constraints(w):
                return LayoutConstraints(AvailableSize(w, True), AvailableSize(80, True))

            renderer = KivyRenderer(
                sfle_constraints=constraints(160), engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Text(
                    "One two three four five six seven eight nine ten "
                    "eleven twelve thirteen fourteen fifteen sixteen.",
                    key="text", layout_width="100%", flex_shrink=0,
                ),
                Button("Below", key="below", layout_width="50px",
                       layout_height="20px", flex_basis="50px",
                       flex_shrink=0),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            label = root.children[0].handle.widget
            button = root.children[1].handle.widget
            wide_height = label.height
            assert wide_height > 0, wide_height
            assert label.width == 160
            assert label.text_size[0] == 160
            wide_button_y = button.y
            # Native geometry must reproduce SFLE's parent-relative projection.
            assert renderer.sfle_result.geometry_commit_error <= 1
            assert renderer._sfle_physical_commit_error <= 1

            renderer.set_sfle_constraints(constraints(90))
            renderer.commit_layout(root)
            narrow_height = label.height
            assert narrow_height > wide_height, (wide_height, narrow_height)
            assert label.width == 90
            assert label.text_size[0] == 90
            assert button.y < wide_button_y, (button.y, wide_button_y)
            assert root.children[0].handle.widget is label
            assert renderer.sfle_result.geometry_commit_error <= 1

            renderer.set_sfle_constraints(constraints(160))
            renderer.commit_layout(root)
            assert label.height == wide_height, (label.height, wide_height)
            assert button.y == wide_button_y
            assert label.text_size[0] == 160
            assert root.children[1].handle.widget is button
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_link_badge_divider_and_spacer_native_geometry(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.button import Button as KivyButton
            from kivy.uix.widget import Widget
            from psx import Flex, Link, Badge, Divider, Spacer, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(340, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            events = []
            def declaration(text, thickness):
                return Flex(
                    Link(label="Guide", key="link",
                         on_click=lambda: events.append(text),
                         layout_width="72px", layout_height="24px",
                         flex_basis="72px", flex_shrink=0),
                    Badge(label=text, key="badge", layout_width="78px",
                          layout_height="24px", flex_basis="78px", flex_shrink=0),
                    Divider(thickness=thickness, key="divider",
                            layout_width="34px", layout_height=f"{thickness}px",
                            flex_basis="34px", flex_shrink=0),
                    Spacer(key="spacer", flex_grow=1, flex_basis="0px",
                           layout_height="10px"),
                    Button("End", key="end", layout_width="30px",
                           layout_height="20px", flex_basis="30px", flex_shrink=0),
                    width="340px", height="80px", direction="row", gap=6,
                    align_items="flex-start",
                )
            root = tree.render(declaration("READY", 3))
            widgets = [item.handle.widget for item in root.children]
            link, badge, divider, spacer, end = widgets
            assert isinstance(link, KivyButton)
            assert isinstance(divider, Widget)
            assert all(w.parent is root.handle.widget for w in widgets)
            assert all(tuple(w.size_hint) == (None, None) for w in widgets)
            expected = (
                (0, 56, 72, 24), (78, 56, 78, 24),
                (162, 77, 34, 3), (202, 70, 102, 10),
                (310, 60, 30, 20),
            )
            actual = tuple(tuple(w.pos) + tuple(w.size) for w in widgets)
            assert actual == expected, (actual, expected)
            assert renderer.sfle_result.geometry_commit_error <= 1
            link.dispatch("on_release")
            assert events == ["READY"], events
            root = tree.render(declaration("DONE", 5))
            assert all(root.children[i].handle.widget is w
                       for i, w in enumerate(widgets))
            assert tuple(divider.pos) + tuple(divider.size) == (162, 75, 34, 5)
            assert tuple(spacer.pos) + tuple(spacer.size) == (202, 70, 102, 10)
            link.dispatch("on_release")
            assert events == ["READY", "DONE"], events
            assert renderer.sfle_result.geometry_commit_error <= 1
            tree.unmount()
            assert renderer.sfle_result is None
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_switch_spinbox_select_native_interaction_and_sfle_geometry(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.spinner import Spinner
            from psx import Flex, Switch, SpinBox, Select
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(380, True), AvailableSize(80, True),
                ),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            calls = []

            def view(tag, checked=False, value=2, selected="a"):
                return Flex(
                    Switch(
                        key="sw", label="Network", checked=checked,
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
                    direction="row", width="380px", height="80px", gap=6,
                    align_items="flex-start",
                )

            root = tree.render(view("before"))
            sw, spin, select = widgets = [item.handle.widget for item in root.children]
            assert isinstance(sw, BoxLayout)
            assert isinstance(spin, BoxLayout)
            assert isinstance(select, Spinner)
            actual = tuple(tuple(w.pos) + tuple(w.size) for w in widgets)
            expected = ((0, 48, 80, 32), (86, 44, 130, 36), (222, 46, 110, 34))
            assert actual == expected, (actual, expected)
            assert all(w.parent is root.handle.widget for w in widgets)
            assert all(tuple(w.size_hint) == (None, None) for w in widgets)
            assert renderer.sfle_result.geometry_commit_error <= 1
            sw._psx_control.dispatch("on_release")
            spin._psx_parts[2].dispatch("on_release")
            select.text = "Beta"
            assert calls == [
                ("switch", "before", True),
                ("spin", "before", 3),
                ("select", "before", "b"),
            ], calls

            updated = tree.render(view("after", True, 3, "b"))
            assert all(updated.children[i].handle.widget is w
                       for i, w in enumerate(widgets))
            assert spin._psx_parts[1].text == "3"
            assert select.text == "Beta"
            assert len(calls) == 3, calls
            sw._psx_control.dispatch("on_release")
            spin._psx_parts[2].dispatch("on_release")
            select.text = "Alpha"
            assert calls[3:] == [
                ("switch", "after", False),
                ("spin", "after", 4),
                ("select", "after", "a"),
            ], calls
            assert renderer.sfle_result.geometry_commit_error <= 1
            tree.unmount()
            assert renderer.sfle_result is None
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_structural_box_radio_group_and_labeled_divider_use_sfle(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.widget import Widget
            from psx import Button, Divider, Flex, Radio, RadioGroup, Text
            from psx.core.vnode import Box
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(340, True), AvailableSize(300, True),
                ), engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            events = []
            root = tree.render(Flex(
                Box(Flex(
                    Button("Nested", key="nested", layout_width="40px",
                           layout_height="20px", flex_basis="40px", flex_shrink=0),
                    width="100%", height="100%", align_items="flex-start",
                ), key="box"),
                RadioGroup(
                    Radio("a", label="Alpha", key="a", layout_width="70px",
                          layout_height="24px", flex_basis="24px", flex_shrink=0),
                    Radio("b", label="Beta", key="b", layout_width="70px",
                          layout_height="24px", flex_basis="24px", flex_shrink=0),
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
            assert isinstance(box, Widget)
            assert isinstance(group, Widget)
            assert isinstance(divider, Widget)
            assert inner.parent is box
            assert radio_a.parent is group
            assert radio_b.parent is group
            assert label.parent is divider
            assert all(tuple(w.size_hint) == (None, None)
                       for w in (box, group, divider, radio_a, radio_b))
            assert tuple(label.size)[0] > 0
            assert group._psx_radios["a"].active
            assert renderer.sfle_result.geometry_commit_error <= 1
            group._psx_radios["b"].active = True
            assert events == ["b"], events
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_scroll_basic_sfle_viewport_and_explicit_content_root(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.scrollview import ScrollView
            from psx import Button, Flex, Scroll
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(300, True), AvailableSize(100, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Scroll(
                    Flex(
                        Button("Inside", key="inside",
                               layout_width="40px", layout_height="20px",
                               flex_basis="40px", flex_shrink=0),
                        direction="row", width="100%", height="100%",
                        align_items="flex-start", key="content",
                    ),
                    key="scroll", direction="vertical", width=120, height=80,
                    layout_width="120px", layout_height="80px",
                    flex_basis="120px", flex_shrink=0,
                ),
                direction="row", width="300px", height="100px",
                align_items="flex-start",
            ))
            scroll = root.children[0].handle.widget
            content = root.children[0].children[0].handle.widget
            child = root.children[0].children[0].children[0].handle.widget
            assert isinstance(scroll, ScrollView)
            assert content.parent is scroll._psx_content
            assert child.parent is content
            assert tuple(scroll.pos) + tuple(scroll.size) == (0, 20, 120, 80)
            assert tuple(content.pos) + tuple(content.size) == (0, 0, 120, 80)
            assert tuple(child.pos) + tuple(child.size) == (0, 60, 40, 20)
            assert renderer.sfle_result.geometry_commit_error <= 1
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_image_intrinsic_source_and_native_sfle_geometry(self):
        script = textwrap.dedent(r"""
            import struct
            import tempfile
            import zlib
            from pathlib import Path
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.image import Image as KivyImage
            from psx import Flex, Image, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.errors import SFLEError
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def png(path, width, height):
                def chunk(kind, data):
                    return (struct.pack(">I", len(data)) + kind + data
                            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
                row = b"\x00" + b"\xff\x33\x66\xff" * width
                Path(path).write_bytes(
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(row * height))
                    + chunk(b"IEND", b"")
                )

            limits = LayoutConstraints(
                AvailableSize(160, True), AvailableSize(100, True),
            )
            with tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "native.png")
                png(path, 24, 12)
                renderer = KivyRenderer(sfle_constraints=limits, engine=PythonLayoutEngine())
                reconcile = Reconciler(renderer)
                def below():
                    return Button("Below", key="below", layout_width="40px",
                                  layout_height="20px", flex_basis="20px",
                                  flex_shrink=0)
                root = reconcile.render(Flex(
                    Image(path, key="img", fit="contain"),
                    below(), direction="column", width="100%", height="100%",
                    align_items="flex-start",
                ))
                widget = root.children[0].handle.widget
                button = root.children[1].handle.widget
                assert isinstance(widget, KivyImage)
                assert widget.parent is root.handle.widget
                assert (widget.width, widget.height) == (24, 12)
                assert abs(button.y - 68) <= 1, button.y
                assert tuple(widget.size_hint) == (None, None)
                assert renderer.sfle_result.geometry_commit_error <= 1
                root = reconcile.render(Flex(
                    Image(path, key="img", fit="cover",
                          layout_width="60px", layout_height="30px"),
                    below(), direction="column", width="100%", height="100%",
                    align_items="flex-start",
                ))
                assert root.children[0].handle.widget is widget
                assert tuple(widget.size) == (60, 30)
                assert abs(button.y - 50) <= 1, button.y
                assert widget.fit_mode == "cover"
                assert renderer.sfle_result.geometry_commit_error <= 1
                reconcile.unmount()
                assert renderer.sfle_result is None
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_textarea_native_width_reflow_and_editing(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from kivy.core.window import Window
            from kivy.uix.textinput import TextInput
            from psx import Flex, TextArea, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def constraints(w=160, h=500):
                return LayoutConstraints(AvailableSize(w, True),
                                         AvailableSize(h, True))
            def below():
                # Column's main axis is vertical: flex-basis must describe
                # the intended height, not the button's 50px inline width.
                return Button("Below", key="below", layout_width="50px",
                              layout_height="20px", flex_basis="20px",
                              flex_shrink=0)

            words = (
                "Alpha bravo charlie delta echo foxtrot golf hotel india "
                "juliet kilo lima mike november oscar papa quebec romeo sierra tango."
            )
            renderer = KivyRenderer(
                sfle_constraints=constraints(), engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            events = []
            root = tree.render(Flex(
                TextArea(value=words, key="edit", on_change=events.append,
                         layout_width="100%", flex_shrink=0),
                below(), direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            edit, button = [node.handle.widget for node in root.children]
            assert isinstance(edit, TextInput) and edit.multiline
            assert edit.parent is root.handle.widget
            assert edit.size_hint == [None, None] or edit.size_hint == (None, None)
            assert edit.text == words
            assert edit.width == 160
            wide_height = edit.height
            assert wide_height > 0
            assert abs(button.y - (500 - wide_height - 20)) <= 1
            edit.select_text(1, 6)
            selection = edit.selection_text
            assert selection
            renderer.set_sfle_constraints(constraints(90))
            renderer.commit_layout(root)
            assert edit.width == 90
            assert edit.height > wide_height, (wide_height, edit.height)
            assert abs(button.y - (500 - edit.height - 20)) <= 1
            assert edit.text == words
            assert edit.selection_text == selection
            assert root.children[0].handle.widget is edit
            assert renderer.sfle_result.geometry_commit_error <= 1
            renderer.set_sfle_constraints(constraints())
            renderer.commit_layout(root)
            assert edit.height == wide_height
            assert abs(button.y - (500 - wide_height - 20)) <= 1
            assert events == []

            previous_generation = renderer.sfle_result.generation
            edit.text = words + " " + " ".join(["Native typing"] * 16)
            Clock.tick()
            Clock.tick()
            assert renderer._sfle_textarea_error is None
            assert renderer.sfle_result.generation > previous_generation
            assert edit.height > wide_height
            assert abs(button.y - (500 - edit.height - 20)) <= 1
            assert edit.parent is root.handle.widget
            assert events == [edit.text], events
            tree.unmount()
            assert renderer.sfle_result is None
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_textarea_css_height_remains_fixed_when_width_changes(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from kivy.uix.textinput import TextInput
            from psx import Flex, TextArea, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def limits(w):
                return LayoutConstraints(AvailableSize(w, True),
                                         AvailableSize(100, True))
            renderer = KivyRenderer(
                sfle_constraints=limits(160), engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                TextArea(value="One two three four five six seven eight nine",
                         key="edit", layout_width="100%", layout_height="36px"),
                Button("B", key="below", layout_width="40px", layout_height="20px"),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            editor, below = (node.handle.widget for node in root.children)
            assert isinstance(editor, TextInput)
            assert editor.height == 36
            assert below.y == 100 - 36 - 20
            renderer.set_sfle_constraints(limits(90))
            renderer.commit_layout(root)
            assert editor.width == 90 and editor.height == 36
            assert below.y == 100 - 36 - 20
            editor.text += " additional words repeated repeatedly"
            Clock.tick()
            Clock.tick()
            assert editor.height == 36
            assert below.y == 100 - 36 - 20
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_native_root_and_sdl2_window_resize_automatically_reflow_sfle(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.core.window import Window
            from kivy.clock import Clock
            from psx import Flex, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def bounds(w, h):
                return LayoutConstraints(AvailableSize(w, True), AvailableSize(h, True))

            class CountingEngine:
                def __init__(self):
                    self.calls = 0
                def compute(self, snapshot):
                    self.calls += 1
                    return PythonLayoutEngine().compute(snapshot)

            def item(name, width):
                return Button(name, key=name, layout_width=f"{width}px",
                              layout_height="20px", flex_basis=f"{width}px",
                              flex_shrink=0)

            engine = CountingEngine()
            renderer = KivyRenderer(sfle_constraints=bounds(160, 80), engine=engine)
            tree = Reconciler(renderer)
            mounted = tree.render(Flex(
                item("Left", 30), item("Right", 20),
                width="100%", height="100%",
                direction="row", justify_content="space-between",
                align_items="flex-start",
            ))
            host = mounted.handle.widget
            left, right = [child.handle.widget for child in mounted.children]
            assert engine.calls == 1
            assert (right.x, right.y, right.width, right.height) == (140, 60, 20, 20)

            # Actual native Kivy size dispatch, coalesced on the toolkit Clock.
            host.size = (210, 100)
            host.size = (260, 120)
            assert engine.calls == 1
            Clock.tick()
            assert renderer._sfle_resize_error is None
            assert engine.calls == 2, engine.calls
            assert (renderer._sfle_constraints.width.value,
                    renderer._sfle_constraints.height.value) == (260, 120)
            assert (right.x, right.y, right.width, right.height) == (240, 100, 20, 20)
            assert mounted.children[0].handle.widget is left
            assert mounted.children[1].handle.widget is right

            # Mount into the real SDL2 Window; Kivy's Window resize
            # notification now controls this SFLE-owned root widget.
            Window.add_widget(host)
            try:
                assert host.parent is Window
                Window.dispatch("on_resize", 280, 140)
                Clock.tick()
                assert renderer._sfle_resize_error is None
                assert engine.calls == 3, engine.calls
                assert tuple(host.size) == (280, 140)
                assert (right.x, right.y, right.width, right.height) == (260, 120, 20, 20)
                assert renderer.sfle_result.geometry_commit_error <= 1
            finally:
                Window.remove_widget(host)

            tree.unmount()
            assert renderer._sfle_mounted_root is None
            assert not renderer._sfle_window_bound
            host.size = (310, 170)
            Clock.tick()
            assert engine.calls == 3
            assert renderer.sfle_result is None
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_real_kivy_native_bottom_left_geometry_and_reconciliation(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.core.window import Window
            from kivy.clock import Clock
            from kivy.uix.widget import Widget
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.label import Label
            from kivy.uix.button import Button as KivyButton

            from psx import Flex, Text, Button, Checkbox, Slider, Spacer, Row, component, use_state, psx
            from psx.core.native import Native
            from psx.core.vnode import create_element
            from psx.sfle.f3_external import SFLEExternalPort
            from psx.sfle.model import IntrinsicSizes, Rect
            from psx.renderers.kivy.kivy import KivyHandle
            from psx.core.reconcile import Reconciler
            from psx.core.errors import RendererCapabilityError
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.errors import SFLEError, DiagnosticCode
            from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutResult

            assert Window is not None, "Real Kivy SDL2 Window provider required"

            def limits(width=160, height=80):
                return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))

            def item(label, key, width):
                return Button(label, key=key, layout_width=f"{width}px",
                              layout_height="20px", flex_basis=f"{width}px",
                              flex_shrink=0)

            def create():
                renderer = KivyRenderer(sfle_constraints=limits(),
                                        engine=PythonLayoutEngine())
                return renderer, Reconciler(renderer)

            def cleanup(renderer, reconciler):
                reconciler.unmount()
                assert renderer.sfle_result is None

            # Parent-relative Y reversal: top-left SFLE y=0, Kivy y=80-0-20=60.
            backend, tree = create()
            root = tree.render(Flex(
                Text("Left", key="left", layout_width="40px",
                     layout_height="20px", flex_basis="40px", flex_shrink=0),
                item("Right", "right", 30),
                direction="row", width="160px", height="80px",
                gap=8, align_items="flex-start",
            ))
            host = root.handle.widget
            assert type(host) is Widget and not isinstance(host, BoxLayout)
            label, button = (instance.handle.widget for instance in root.children)
            assert isinstance(label, Label) and isinstance(button, KivyButton)
            assert (label.parent, button.parent) == (host, host)
            assert (label.x, label.y, label.width, label.height) == (0, 60, 40, 20)
            assert (button.x, button.y, button.width, button.height) == (48, 60, 30, 20)
            assert list(host.children) == [button, label]
            assert label.size_hint == [None, None] or label.size_hint == (None, None)
            assert button.size_hint == [None, None] or button.size_hint == (None, None)
            assert backend.sfle_result.geometry_commit_error == 0
            assert len(backend.sfle_result.boxes) == 3
            # Exercise the actual SDL2 window parent, not just detached Widgets.
            Window.add_widget(host)
            try:
                Clock.tick()
                assert (label.x, label.y, label.width, label.height) == (0, 60, 40, 20)
                assert (button.x, button.y, button.width, button.height) == (48, 60, 30, 20)
                assert type(host) is Widget and host.parent is Window
            finally:
                Window.remove_widget(host)
            cleanup(backend, tree)

            # Multiple nested frames (not global/window flip).
            backend, tree = create()
            # CSS content-box 140x60 + 10px padding each side = 160x80 border-box.
            root = tree.render(psx('''
                <Flex direction="column" width="140px" height="60px"
                      padding={10} align_items="flex-start">
                    <Flex direction="row" width="120px" height="40px"
                          gap={6} align_items="flex-start">
                        <Button label="A" key="a" layout_width="30px"
                                layout_height="15px" flex_basis="30px"
                                flex_shrink={0} />
                        <Button label="B" key="b" layout_width="20px"
                                layout_height="15px" flex_basis="20px"
                                flex_shrink={0} />
                    </Flex>
                </Flex>
            '''))
            nested = root.children[0].handle.widget
            a, b = [i.handle.widget for i in root.children[0].children]
            assert type(nested) is Widget and not isinstance(nested, BoxLayout)
            assert nested.parent is root.handle.widget
            assert (nested.x, nested.y, nested.width, nested.height) == (10, 30, 120, 40), tuple(nested.pos) + tuple(nested.size)
            assert (a.x, a.y, a.width, a.height) == (0, 25, 30, 15)
            assert (b.x, b.y, b.width, b.height) == (36, 25, 20, 15)
            cleanup(backend, tree)

            # Moving keyed children must retain the exact Kivy native Widget objects.
            backend, tree = create()
            root = tree.render(Flex(item("A", "a", 30), item("B", "b", 20),
                                    width=160, height=80, gap=4, align_items="flex-start"))
            a, b = [i.handle.widget for i in root.children]
            assert (a.x, b.x) == (0, 34)
            after = tree.render(Flex(item("B", "b", 20), item("A", "a", 30),
                                     width=160, height=80, gap=9, align_items="flex-start"))
            assert after.children[0].handle.widget is b
            assert after.children[1].handle.widget is a
            assert (b.x, a.x) == (0, 29)
            assert backend.sfle_result.generation == 2
            cleanup(backend, tree)

            # Reconciler hooks/scheduler/events on the Kivy Clock thread.
            setters = []
            clicks = []
            @component
            def Counter():
                value, set_value = use_state(0)
                setters.append(set_value)
                return Flex(Button("Click", key="stable",
                                   on_click=lambda: clicks.append(value),
                                   layout_width=f"{20+value*10}px",
                                   layout_height="20px",
                                   flex_basis=f"{20+value*10}px",
                                   flex_shrink=0),
                            width=160, height=80)
            backend, tree = create()
            root = tree.render(Counter())
            handle = root.children[0].children[0].handle
            handle.widget.dispatch("on_release")
            assert clicks == [0]
            setters[-1](2)
            Clock.tick()
            assert root.children[0].children[0].handle is handle
            assert handle.widget.width == 40
            handle.widget.dispatch("on_release")
            assert clicks == [0, 2]
            cleanup(backend, tree)

            # Viewport change: recalculates in place, with no native remount.
            backend, tree = create()
            root = tree.render(Flex(
                item("A", "a", 30), width="100%", height="100%",
                align_items="flex-start",
            ))
            native = root.children[0].handle.widget
            backend.set_sfle_constraints(limits(240, 120))
            backend.commit_layout(root)
            assert root.children[0].handle.widget is native
            assert tuple(root.handle.widget.size) == (240, 120)
            assert (native.x, native.y, native.width, native.height) == (0, 100, 30, 20)
            cleanup(backend, tree)

            # Size-hint native widgets cannot impersonate intrinsic measurements.
            # Fixed px SFLE layout dimensions make Checkbox/Slider/Spacer safe.
            backend, tree = create()
            try:
                tree.render(Flex(Slider(), width=160, height=80))
            except RendererCapabilityError as error:
                assert "explicit pixel layout_width" in str(error)
            else:
                raise AssertionError("Kivy Slider with auto size bypassed capability gate")
            tree.unmount()

            calls = []
            backend, tree = create()
            native_root = tree.render(Flex(
                Checkbox(checked=False, key="checkbox",
                         on_change=calls.append,
                         layout_width="20px", layout_height="16px",
                         flex_basis="20px", flex_shrink=0),
                Slider(value=30, key="slider",
                       layout_width="32px", layout_height="20px",
                       flex_basis="32px", flex_shrink=0),
                Spacer(key="spacer",
                       layout_width="12px", layout_height="8px",
                       flex_basis="12px", flex_shrink=0),
                width=160, height=80, gap=5, align_items="flex-start",
            ))
            check, slider, spacer = [child.handle.widget for child in native_root.children]
            assert tuple(check.pos) + tuple(check.size) == (0, 64, 20, 16)
            assert tuple(slider.pos) + tuple(slider.size) == (25, 60, 32, 20)
            assert tuple(spacer.pos) + tuple(spacer.size) == (62, 72, 12, 8)
            assert not isinstance(native_root.handle.widget, BoxLayout)
            check.active = True
            assert calls == [True]
            assert backend.sfle_result.geometry_commit_error <= 1.0
            cleanup(backend, tree)

            # Native and registered custom leaves have an explicit
            # measure -> projected apply -> readback contract, with no Kivy
            # default size_hint or CSS fallback pretending to be intrinsic.
            external_calls = []
            def external_measure(widget, limits):
                external_calls.append("measure")
                return IntrinsicSizes(10, 20, 8, 14, 20, 14)
            def external_apply(widget, rect):
                external_calls.append(("apply", rect))
                widget.pos = (rect.x, rect.y)
                widget.size = (rect.width, rect.height)
            def external_read(widget):
                external_calls.append("read")
                return Rect(widget.x, widget.y, widget.width, widget.height)
            external_port = SFLEExternalPort(
                external_measure, external_apply, external_read,
            )
            backend, tree = create()
            root = tree.render(Flex(
                Flex(
                    Native(Widget, renderer="kivy", sfle_port=external_port,
                           key="native", layout_width="26px",
                           layout_height="12px", flex_basis="26px",
                           flex_shrink=0),
                    width="90px", height="40px", align_items="flex-start",
                ),
                width="160px", height="80px", align_items="flex-start",
            ))
            inner = root.children[0].handle.widget
            external_widget = root.children[0].children[0].handle.widget
            assert external_widget.parent is inner
            assert tuple(external_widget.pos) + tuple(external_widget.size) == (0, 28, 26, 12)
            assert "measure" in external_calls
            assert ("apply", Rect(0, 28, 26, 12)) in external_calls
            assert "read" in external_calls
            assert backend.sfle_result.geometry_commit_error <= 1.0
            cleanup(backend, tree)

            backend, tree = create()
            class CustomAdapter:
                sfle_port = external_port
                def create(self, renderer, node, parent):
                    return KivyHandle("CustomTile", Widget(size_hint=(None, None)), {})
                def update(self, renderer, handle, changed, removed):
                    pass
                def destroy(self, renderer, handle):
                    if handle.widget.parent is not None:
                        handle.widget.parent.remove_widget(handle.widget)
                def bind_event(self, renderer, handle, event, slot):
                    raise RendererCapabilityError("Unknown custom event")
                def unbind_event(self, renderer, subscription):
                    pass
            backend.register_adapter("CustomTile", CustomAdapter())
            custom_root = tree.render(Flex(
                create_element("CustomTile", layout_width="30px",
                               layout_height="14px", flex_basis="30px",
                               flex_shrink=0),
                width="160px", height="80px",
            ))
            custom = custom_root.children[0].handle.widget
            assert custom.parent is custom_root.handle.widget
            assert tuple(custom.pos) + tuple(custom.size) == (0, 66, 30, 14)
            assert ("apply", Rect(0, 66, 30, 14)) in external_calls
            cleanup(backend, tree)

            native_created = []
            backend, tree = create()
            def bad_native_factory():
                native_created.append(True)
                return Widget()
            try:
                tree.render(Flex(
                    Native(bad_native_factory, renderer="kivy",
                           layout_width="20px", layout_height="20px"),
                    width="160px", height="80px",
                ))
            except RendererCapabilityError as error:
                assert "Native requires" in str(error)
            else:
                raise AssertionError("Kivy Native without SFLE port was mounted")
            assert not native_created
            tree.unmount()

            # Unported component: no fallback to Kivy BoxLayout.
            backend, tree = create()
            try:
                tree.render(Flex(Row(), width=160, height=80))
            except RendererCapabilityError as error:
                assert "not certified" in str(error)
            else:
                raise AssertionError("Unported Kivy native widget silently mounted")
            tree.unmount()

            # Stale engine identity: fail before native geometry mutation.
            class BadEngine:
                def compute(self, request):
                    correct = PythonLayoutEngine().compute(request)
                    return LayoutResult(1, request.generation + 1, correct.boxes)
            backend = KivyRenderer(sfle_constraints=limits(), engine=BadEngine())
            tree = Reconciler(backend)
            try:
                tree.render(Flex(item("A", "a", 30), width=160, height=80))
            except SFLEError as error:
                assert error.code is DiagnosticCode.INVALID_SNAPSHOT
            else:
                raise AssertionError("Stale SFLE geometry committed")
            assert backend.sfle_result is None
            tree.unmount()

            # G1 no-opt-in still rejects Flex explicitly.
            backend = KivyRenderer()
            tree = Reconciler(backend)
            try:
                tree.render(Flex(width=160, height=80))
            except RendererCapabilityError as error:
                assert "F3-G2 SFLE geometry" in str(error)
            else:
                raise AssertionError("Kivy quietly fell back to BoxLayout")
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        # CI disables console logs globally. Override it in this subprocess
        # so unexpected native Kivy failures expose their Python traceback.
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_all_ported_builtin_lifecycles_keep_native_widget_handles(self):
        """Real SDL2 runtime; each native family gets keyed update and removal."""
        script = textwrap.dedent(r"""
            from pathlib import Path
            from tempfile import TemporaryDirectory
            import base64
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import (Text, Button, Input, Checkbox, TextArea, Slider,
                             Spacer, Divider, Image, ProgressBar, Radio,
                             RadioGroup, Select, Switch, Link, Badge, SpinBox,
                             Scroll, Flex)
            from psx.core.vnode import Box
            from psx.core.vnode import create_element
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            from psx.sfle.f3_native_coverage import G2_LEAF_TYPES

            with TemporaryDirectory() as tmp:
                png = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                       "AAAAC0lEQVR42mP8/x8AAusB9Y9WdmkAAAAASUVORK5CYII=")
                path = Path(tmp) / "pixel.png"
                path.write_bytes(base64.b64decode(png))
                factories = {
                    "Text": lambda: Text("Before"),
                    "Button": lambda: Button("Before"),
                    "Input": lambda: Input(value="Before"),
                    "Checkbox": lambda: Checkbox(),
                    "TextArea": lambda: TextArea("Before"),
                    "Slider": lambda: Slider(value=30),
                    "Spacer": lambda: Spacer(),
                    "Divider": lambda: Divider(),
                    "Image": lambda: Image(str(path)),
                    "ProgressBar": lambda: ProgressBar(value=30),
                    "Radio": lambda: Radio("a", label="Before"),
                    "RadioGroup": lambda: RadioGroup(Radio("a", label="Before")),
                    "Select": lambda: Select(
                        options=[{"label": "A", "value": "a"},
                                 {"label": "B", "value": "b"}], value="a"),
                    "Switch": lambda: Switch(checked=False),
                    "Link": lambda: Link(label="Before"),
                    "Badge": lambda: Badge(label="Before"),
                    "SpinBox": lambda: SpinBox(value=30),
                    "Scroll": lambda: Scroll(Flex(
                        Text("Content", layout_width="30px",
                             layout_height="15px"), width="40px", height="24px")),
                    "Box": lambda: Box(Text("Inside", layout_width="30px",
                                           layout_height="15px")),
                    "Flex": lambda: Flex(Text("Inside", layout_width="30px",
                                             layout_height="15px")),
                }
                native = set(G2_LEAF_TYPES["kivy"]) | {"Flex"}
                assert set(factories) == native, sorted(native ^ set(factories))

                renderer = KivyRenderer(
                    sfle_constraints=LayoutConstraints(
                        AvailableSize(260, True), AvailableSize(90, True)),
                    engine=PythonLayoutEngine(),
                )
                tree = Reconciler(renderer)
                def item(name, width):
                    if name == "Box":
                        return create_element(
                            "Box", Text("Inside", layout_width=f"{width}px",
                                        layout_height="15px"), key="item")
                    base = factories[name]()
                    props = {**dict(base.props), "flex_basis": f"{width}px",
                             "flex_shrink": 0}
                    if name == "Flex":
                        props.update(width=f"{width}px", height="24px")
                    else:
                        props.update(layout_width=f"{width}px", layout_height="24px")
                    return create_element(base.type, *base.children,
                                          key="item", **props)
                def view(name, width, reverse=False):
                    target = item(name, width)
                    peer = Button("Peer", key="peer", layout_width="20px",
                                  layout_height="24px", flex_basis="20px",
                                  flex_shrink=0)
                    return Flex(*((peer, target) if reverse else (target, peer)),
                                width=260, height=90, gap=8,
                                align_items="flex-start")
                for name in sorted(native):
                    tree.unmount()
                    try:
                        first = tree.render(view(name, 60))
                        old = first.children[0]
                        native_widget = old.handle.widget
                        assert native_widget.width == 60, (name, native_widget.size)
                        assert native_widget.height == 24, (name, native_widget.size)
                        second = tree.render(view(name, 80, True))
                        current = second.children[1]
                        assert current is old, name
                        assert current.handle.widget is native_widget, name
                        assert native_widget.width == 80, (name, native_widget.size)
                        assert native_widget.x > second.children[0].handle.widget.x, name
                        tree.render(Flex(
                            Button("Peer", key="peer", layout_width="20px",
                                   layout_height="24px"),
                            width=260, height=90, align_items="flex-start"))
                        assert old.disposed, name
                        assert native_widget.parent is None, name
                    except Exception as error:
                        raise AssertionError(f"Native Kivy lifecycle for {name}: {error}") from error
                tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment, capture_output=True, text=True, timeout=150,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_all_callback_controls_rebind_without_native_remount(self):
        """Actual SDL2 widgets retain their identity and stable callback slot."""
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import (Button, Input, TextArea, Checkbox, Slider, RadioGroup,
                             Radio, Select, Switch, Link, SpinBox, Flex)
            from psx.core.vnode import create_element
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            from psx.sfle.f3_native_coverage import G2_LEAF_TYPES
            from psx.sfle.f3_g2_contracts import EVENTLESS

            callbacks = {
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
            assert set(callbacks) == (set(G2_LEAF_TYPES["kivy"]) | {"Flex"}) - EVENTLESS
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(180, True), AvailableSize(70, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            for name, (base, event, args) in callbacks.items():
                calls = []
                tree.unmount()
                def view(callback):
                    item = create_element(
                        base.type, *base.children, key="control",
                        **{**dict(base.props), event: callback,
                           "layout_width": "70px", "layout_height": "28px",
                           "flex_basis": "70px", "flex_shrink": 0},
                    )
                    return Flex(item, width=180, height=70,
                                align_items="flex-start")
                try:
                    first = tree.render(
                        view(lambda *values: calls.append(("old", values))))
                    instance = first.children[0]
                    native_widget = instance.handle.widget
                    slot = instance.event_slots[event][0]
                    slot.invoke(*args)
                    assert calls == [("old", args)], (name, calls)
                    second = tree.render(
                        view(lambda *values: calls.append(("new", values))))
                    assert second.children[0] is instance, name
                    assert instance.handle.widget is native_widget, name
                    assert instance.event_slots[event][0] is slot, name
                    assert len(instance.event_slots) == 1, name
                    slot.invoke(*args)
                    assert calls == [("old", args), ("new", args)], (name, calls)
                    tree.unmount()
                    slot.invoke(*args)
                    assert len(calls) == 2, name
                except Exception as error:
                    raise AssertionError(f"Kivy event rebinding for {name}: {error}") from error
        """)
        env = dict(os.environ)
        env["KIVY_NO_FILELOG"] = "1"
        env["KIVY_NO_ARGS"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env, capture_output=True, text=True, timeout=150,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

