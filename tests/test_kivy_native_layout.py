"""Native SFLE native Kivy SFLE certification, executed under a real SDL2 provider.

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
    def test_centered_column_blocks_remain_full_width_after_resize(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            def constraints(width):
                return LayoutConstraints(
                    AvailableSize(width, True), AvailableSize(500, True),
                )
            renderer = KivyRenderer(
                sfle_constraints=constraints(500), engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            root = reconciler.render(psx(
                '<div style="display: flex; flex-direction: column; '
                'align-items: center; gap: 16px; height: 100vh">'
                '<h1>Get started</h1>'
                '<p style="background-color: red">Edit src/App.tsx and save to test HMR</p>'
                '<button>Count is 0</button></div>'
            ))
            title, paragraph, button = root.children
            for width in (500, 280, 160, 500):
                renderer.set_sfle_constraints(constraints(width))
                renderer.commit_layout(root)
                for block in (title, paragraph):
                    assert abs(block.handle.widget.width - width) <= 1, (
                        width, block.handle.widget.width,
                    )
                    label = block.children[0].handle.widget
                    assert abs(label.width - width) <= 1, (
                        width, label.width,
                    )
                    assert block.handle.widget.height >= label.height - 1, (
                        block.handle.widget.height, label.height,
                    )
                assert button.handle.widget.width < width
                assert renderer.sfle_result.geometry_commit_error <= 1
            reconciler.unmount()
        """)
        env = dict(os.environ)
        env.update(KIVY_NO_ARGS="1", KIVY_NO_FILELOG="1")
        result = subprocess.run(
            [sys.executable, "-c", script], env=env,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_mixed_inline_span_keeps_one_line_when_available(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            def constraints(width):
                return LayoutConstraints(
                    AvailableSize(width, True), AvailableSize(400, True),
                )
            renderer = KivyRenderer(
                sfle_constraints=constraints(800), engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            root = reconciler.render(psx(
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
            assert abs(prefix.y - span.y) <= 1, (prefix.y, span.y)
            assert abs(suffix.y - span.y) <= 1, (suffix.y, span.y)
            assert prefix.x < span.x < suffix.x, (prefix.x, span.x, suffix.x)
            assert nested.text == "src/App.tsx"
            # The native texture must be paintable inside the assigned width.
            # Geometry order alone missed the screenshot's clipped "src/".
            old_text_size = nested.text_size
            nested.text_size = (None, None)
            nested.texture_update()
            natural = nested.texture_size[0]
            nested.text_size = old_text_size
            nested.texture_update()
            assert nested.width >= natural - 2, (
                "Unpaintable inline Kivy span", nested.width, natural,
                span.width,
            )
            assert abs(paragraph.handle.widget.width - 800) <= 1
            assert renderer.sfle_result.geometry_commit_error <= 1
            for width in (400, 220, 800):
                renderer.set_sfle_constraints(constraints(width))
                renderer.commit_layout(root)
                assert abs(paragraph.handle.widget.width - width) <= 1
                if width >= 400:
                    assert nested.width >= natural - 2, (
                        width, nested.width, natural,
                    )
                assert paragraph.handle.widget.height >= prefix.height - 1
                assert renderer.sfle_result.geometry_commit_error <= 1
            reconciler.unmount()
        """)
        env = dict(os.environ)
        env.update(KIVY_NO_ARGS="1", KIVY_NO_FILELOG="1")
        result = subprocess.run(
            [sys.executable, "-c", script], env=env,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_inline_span_padding_preserves_kivy_glyph_alignment(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            def constraints():
                return LayoutConstraints(
                    AvailableSize(650, True), AvailableSize(350, True),
                )
            renderer = KivyRenderer(
                sfle_constraints=constraints(), engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            for padding in (0, 4, 19):
                root = reconciler.render(psx(
                    '<div style="display:flex; flex-direction:column; align-items:center">'
                    '<p>esto es una <span style="background:#404243; '
                    f'border-radius:4px; padding:{padding}px">hola</span> prueba</p>'
                    '</div>'
                ))
                paragraph = root.children[0]
                span = next(item for item in paragraph.children
                            if item.node.type == "span")
                before = paragraph.children[0].handle.widget
                after = paragraph.children[-1].handle.widget
                inside = span.children[0].handle.widget
                # Kivy uses bottom-left origins. Convert child text line
                # tops into the same paragraph-local coordinate system.
                tops = [
                    before.y + before.height,
                    span.handle.widget.y + inside.y + inside.height,
                    after.y + after.height,
                ]
                assert max(tops) - min(tops) <= 1, (padding, tops)
                assert span.handle.widget.height >= inside.height + 2*padding - 1
                assert renderer.sfle_result.geometry_commit_error <= 1
            reconciler.unmount()
        """)
        env = dict(os.environ)
        env.update(KIVY_NO_ARGS="1", KIVY_NO_FILELOG="1")
        result = subprocess.run(
            [sys.executable, "-c", script], env=env,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_css_background_updates_and_canvas_cleanup(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(240, True), AvailableSize(140, True),
                ),
                engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            mounted = reconciler.render(psx(
                '<div key="same" style="background-color: #112233" />'
            ))
            widget = mounted.handle.widget
            group, redraw, color = widget._psx_css_paint
            assert round(color.r * 255) == 17
            assert round(color.g * 255) == 34
            assert round(color.b * 255) == 51
            changed = reconciler.render(psx(
                '<div key="same" style="background-color: #aabbcc" />'
            ))
            assert changed.handle.widget is widget
            assert widget._psx_css_paint[0] is group
            assert round(color.r * 255) == 170
            reconciler.render(psx('<div key="same" />'))
            assert not hasattr(widget, "_psx_css_paint")
            reconciler.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_FILELOG"] = "1"
        env["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env, capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_css_dimensions_commit_to_kivy_widget_geometry(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(240, True), AvailableSize(140, True),
                ),
                engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            root = reconciler.render(psx(
                '<div>'
                '<button style="width: 45px; height: 15px; margin-left: 3px; padding: 2px; border-width: 1px">Save</button></div>'
            ))
            assert round(root.children[0].handle.widget.width) == 51
            assert round(root.children[0].handle.widget.height) == 21
            assert round(root.children[0].handle.widget.x) == 3
            assert renderer.sfle_result.geometry_commit_error <= 1
            reconciler.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_html_block_uses_cinnamon_native_positions(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(240, True), AvailableSize(140, True),
                ),
                engine=PythonLayoutEngine(),
            )
            reconciler = Reconciler(renderer)
            root = reconciler.render(psx(
                '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
            ))
            alpha, beta = (item.handle.widget for item in root.children)
            assert alpha.parent is root.handle.widget
            assert root.handle.widget.size_hint == [None, None]
            assert round(root.handle.widget.width) == 240
            assert round(root.handle.widget.height) == 140
            assert 0 < round(alpha.width) < 240
            assert 0 < round(beta.width) < 240
            assert round(alpha.y) == round(beta.y)
            assert round(beta.x) == round(alpha.x + alpha.width)
            assert renderer.sfle_result.geometry_commit_error <= 1
            updated = reconciler.render(psx(
                '<div><button key="b">Beta</button><button key="a">Alpha</button></div>'
            ))
            assert updated.children[0].handle.widget is beta
            assert updated.children[1].handle.widget is alpha
            assert round(beta.y) == round(alpha.y)
            assert round(alpha.x) == round(beta.x + beta.width)
            reconciler.unmount()
            assert alpha.parent is None and beta.parent is None
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

    def test_mounted_kivy_flex_consumes_canonical_item_lengths(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.lengths import Length
            from psx.sfle.model import AvailableSize, LayoutConstraints
            from psx.sfle.native_layout_snapshot import PreparedNativeLayoutSnapshot

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            original = PreparedNativeLayoutSnapshot.canonical_snapshot
            observed = []

            def record(prepared):
                snapshot = original(prepared)
                observed.append(snapshot)
                return snapshot

            def button(label, key, width):
                return Button(
                    label, key=key, layout_width=f"{width}px",
                    layout_height="20px", flex_basis=f"{width}px",
                    flex_shrink=0,
                )

            with patch.object(PreparedNativeLayoutSnapshot, "canonical_snapshot", record):
                root = tree.render(Flex(
                    button("Left", "left", 40),
                    button("Right", "right", 30),
                    direction="row", gap=8, width="160px", height="80px",
                    align_items="flex-start",
                ))
            assert observed, "Mounted Kivy must consume canonical lengths"
            style = dict(observed[-1].nodes[1].style)
            assert style["layout_width"] == Length.px(40), style
            assert style["layout_height"] == Length.px(20), style
            left, right = (child.handle.widget for child in root.children)
            assert tuple(left.pos) + tuple(left.size) == (0, 60, 40, 20)
            assert tuple(right.pos) + tuple(right.size) == (48, 60, 30, 20)
            assert renderer.sfle_result.geometry_commit_error <= 1
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_kivy_intrinsic_controls_without_pixel_bounds(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Flex, Input, Checkbox, ProgressBar
            from psx.core.errors import RendererCapabilityError
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

    def test_native_kivy_wheel_and_nested_edge_chaining(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.widget import Widget
            from psx.renderers.kivy.scroll import _PSXScrollView
            from types import SimpleNamespace

            def scroll(width, height, content_width, content_height):
                view = _PSXScrollView(size_hint=(None, None),
                                      size=(width, height))
                content = Widget(size_hint=(None, None),
                                 size=(content_width, content_height))
                view.add_widget(content)
                view._psx_content = content
                view._psx_sfle_scroll = True
                view._psx_props = {"enabled": True, "direction": "vertical"}
                view.scroll_y = 1.0
                return view, content

            outer, outer_content = scroll(160, 100, 160, 300)
            inner, inner_content = scroll(120, 80, 120, 200)
            outer_content.add_widget(inner)
            inner.scroll_y = 0.0
            remaining = inner._psx_scroll_delta(0, 45)
            assert remaining == (0.0, 0.0)
            assert abs(outer.scroll_y - (1 - 45 / 200)) < 1e-6
            assert inner.scroll_y == 0.0
            first = outer.scroll_y
            touch = SimpleNamespace(is_mouse_scrolling=True,
                                    button="scrolldown",
                                    pos=(inner.center_x, inner.center_y))
            assert inner.on_touch_down(touch) is True
            assert outer.scroll_y < first
            # No scroll host claims a delta after all ancestors reach a bound.
            outer.scroll_y = 0.0
            assert inner._psx_scroll_delta(0, 48) == (0.0, 48.0)
            outer.scroll_y = 1.0
            from unittest.mock import patch
            from kivy.uix.scrollview import ScrollView
            # Native Kivy owns kinetic pan mechanics. Exercise PSX's edge
            # residual around that operation without synthesizing a second
            # native physics solver.
            with patch.object(ScrollView, "on_scroll_move", return_value=True):
                touch_move = SimpleNamespace(dx=0.0, dy=-30.0)
                assert inner.on_scroll_move(touch_move) is True
            assert abs(outer.scroll_y - (1 - 30 / 200)) < 1e-6
            outer_content.remove_widget(inner)
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

    def test_scroll_unmount_detaches_kivy_viewport(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex, Scroll
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(300, True), AvailableSize(200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Scroll(Flex(Button("Inside", key="inside",
                                   layout_width="40px", layout_height="20px",
                                   flex_shrink=0),
                            direction="row", width="300px", height="200px",
                            key="content", align_items="flex-start"),
                       key="scroll", direction="both",
                       layout_width="120px", layout_height="80px",
                       flex_basis="120px", flex_shrink=0),
                direction="row", width="300px", height="200px",
                align_items="flex-start",
            ))
            view = root.children[0].handle.widget
            content = view._psx_content
            assert content.parent is view
            tree.unmount()
            assert view.parent is None
            assert renderer._sfle_mounted_root is None
        """)
        env = dict(os.environ)
        env["KIVY_NO_FILELOG"] = "1"
        env["KIVY_NO_ARGS"] = "1"
        env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_scroll_native_kivy_failure_restores_offsets(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex, Scroll
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            from psx.sfle import native_scroll_hosts

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(300, True), AvailableSize(200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Scroll(Flex(Button("Inside", key="inside",
                                   layout_width="40px", layout_height="20px",
                                   flex_shrink=0),
                            direction="row", width="300px", height="200px",
                            key="content", align_items="flex-start"),
                       key="scroll", direction="both",
                       layout_width="120px", layout_height="80px",
                       flex_basis="120px", flex_shrink=0),
                direction="row", width="300px", height="200px",
                align_items="flex-start",
            ))
            view = root.children[0].handle.widget
            view.scroll_x, view.scroll_y = 0.5, 0.5
            content_size = tuple(view._psx_content.size)
            original = native_scroll_hosts.apply_kivy_scroll

            def fail(host, binding, offset):
                original(host, binding, offset)
                host.scroll_x, host.scroll_y = 0.0, 1.0
                raise RuntimeError("injected Kivy native failure")

            with patch.object(native_scroll_hosts, "apply_kivy_scroll", side_effect=fail):
                try:
                    renderer.commit_layout(root)
                except RuntimeError as exc:
                    assert "injected Kivy" in str(exc)
                else:
                    raise AssertionError("Injected native failure was swallowed")
            assert abs(view.scroll_x - 0.5) < 1e-6
            assert abs(view.scroll_y - 0.5) < 1e-6
            assert tuple(view._psx_content.size) == content_size
            tree.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_FILELOG"] = "1"
        env["KIVY_NO_ARGS"] = "1"
        env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_scroll_mounted_reflow_preserves_logical_offsets(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex, Scroll
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(300, True), AvailableSize(200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Scroll(Flex(
                    Button("Inside", key="inside", layout_width="40px",
                           layout_height="20px", flex_shrink=0),
                    direction="row", width="300px", height="200px",
                    key="content", align_items="flex-start"),
                    direction="both", key="scroll",
                    layout_width="120px", layout_height="80px",
                    flex_basis="120px", flex_shrink=0),
                direction="row", width="300px", height="200px",
                align_items="flex-start",
            ))
            scroll = root.children[0].handle.widget
            child = root.children[0].children[0].children[0].handle.widget
            scroll.scroll_x = 0.5
            scroll.scroll_y = 0.5
            renderer.commit_layout(root)
            assert abs(scroll.scroll_x - 0.5) < 1e-6
            assert abs(scroll.scroll_y - 0.5) < 1e-6
            assert root.children[0].children[0].children[0].handle.widget is child
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
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_scroll_overflow_native_extent_and_logical_offsets(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex, Scroll
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(300, True), AvailableSize(200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Scroll(Flex(
                    Button("Inside", key="inside",
                           layout_width="40px", layout_height="20px",
                           flex_shrink=0),
                    direction="row", width="300px", height="200px",
                    align_items="flex-start", key="content",
                ), key="scroll", direction="both",
                    layout_width="120px", layout_height="80px",
                    flex_basis="120px", flex_shrink=0),
                direction="row", width="300px", height="200px",
                align_items="flex-start",
            ))
            scroll = root.children[0].handle.widget
            content = root.children[0].children[0].handle.widget
            assert tuple(scroll._psx_content.size) == (300, 200)
            assert content.parent is scroll._psx_content
            assert tuple(content.size) == (300, 200)
            assert tuple(content.pos) == (0, 0)
            assert scroll.scroll_x == 0.0
            assert scroll.scroll_y == 1.0
            assert renderer.sfle_result.geometry_commit_error <= 1
            from psx.sfle.native_scroll_hosts import (
                apply_kivy_scroll, binding_from_host,
            )
            from psx.sfle.scroll_offsets import ScrollOffset
            from psx.sfle.model import Rect
            binding = binding_from_host(
                scroll._psx_props, Rect(0, 0, 120, 80),
                Rect(0, 0, 300, 200),
            )
            applied = apply_kivy_scroll(scroll, binding, ScrollOffset(90, 60))
            assert applied.offset == ScrollOffset(90, 60)
            assert abs(scroll.scroll_x - 0.5) < 1e-6
            assert abs(scroll.scroll_y - 0.5) < 1e-6
            assert tuple(content.size) == (300, 200)
            button = root.children[0].children[0].children[0].handle.widget
            renderer.commit_layout(root)
            assert abs(scroll.scroll_x - 0.5) < 1e-6
            assert abs(scroll.scroll_y - 0.5) < 1e-6
            assert root.children[0].children[0].children[0].handle.widget is button
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
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

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

    def test_run_attaches_cinnamon_root_at_full_window_size(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.core.window import Window
            from kivy.clock import Clock
            from psx import Flex, Button
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
            root = tree.render(Flex(
                Button("Resize", layout_width="70px", layout_height="25px"),
                width="100%", height="100%", direction="column",
            ))
            host = root.handle.widget
            assert renderer._sfle_watched_widget is host
            original_size = tuple(host.size)
            assert original_size == (160, 80), original_size
            Window.size = (780, 540)
            def fake_run_touch_app(widget):
                Window.add_widget(widget)
                try:
                    Clock.tick()
                    Clock.tick()
                    assert tuple(widget.size) == tuple(Window.size), (
                        tuple(widget.size), tuple(Window.size))
                    assert (renderer._sfle_constraints.width.value,
                            renderer._sfle_constraints.height.value) == tuple(Window.size)
                    assert renderer._sfle_resize_error is None
                    Window.dispatch("on_resize", 900, 600)
                    Clock.tick()
                    assert tuple(widget.size) == (900, 600)
                    assert renderer._sfle_constraints.width.value == 900
                    assert renderer._sfle_constraints.height.value == 600
                    assert renderer._sfle_resize_error is None
                finally:
                    Window.remove_widget(widget)

            with patch("psx.renderers.kivy.kivy.runTouchApp", fake_run_touch_app):
                assert renderer.run() == 0
            tree.unmount()
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_grid_sidebar_content_appears_at_top_of_viewport(self):
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(1188, True), AvailableSize(600, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height: 100vh; background: red;">
                    <Grid gap="0px">
                        <GridItem span="2">
                            <div style="height: 100vh; display: flex; flex-direction: column; padding: 20px 12px; background: #20242d;">
                                <h5 style="font-size: 18px">Mi panel</h5>
                                <div style="display: flex; flex-direction: column; gap: 10px;">
                                    <button style="height: 38px;">Resumen</button>
                                    <button style="height: 38px;">Usuarios</button>
                                </div>
                            </div>
                        </GridItem>
                    </Grid>
                </div>
            """))
            def walk(node):
                yield node
                for child in node.children:
                    yield from walk(child)
            widgets = [(node.node.type,
                        node.handle.widget if node.handle is not None else None)
                       for node in walk(root)]
            print("SIDE_GEOMETRY", [(name, tuple(w.pos), tuple(w.size))
                  for name, w in widgets if w is not None], flush=True)
            buttons = [w for name, w in widgets if name in ("button", "Button")]
            assert len(buttons) == 2, widgets
            # Native coordinate origin is bottom-left. Header and buttons
            # belong near the TOP of a 600px viewport, not its bottom edge.
            for button in buttons:
                top = button.to_window(button.width / 2, button.height, relative=True)[1]
                assert top > 380, (top, widgets)
            tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_css_fixed_heights_use_cinnamon_not_kivy_defaults(self):
        """CSS height:30px must appear in native geometry without feedback hangs."""
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from kivy.core.window import Window
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(800, True), AvailableSize(600, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh">
                    <div style="height:30px; background:red"><p>First</p></div>
                    <div style="height:50px; background:blue"><p>Second</p></div>
                    <button style="height:38px; font-size:15px; padding:0px 10px">Button</button>
                </div>
            """))
            first, second, button = root.children
            assert abs(first.handle.widget.height - 30) <= 1, first.handle.widget.size
            assert abs(second.handle.widget.height - 50) <= 1, second.handle.widget.size
            assert abs(button.handle.widget.height - 38) <= 1, button.handle.widget.size
            assert abs(button.handle.widget.font_size - 15) <= 0.01
            assert list(button.handle.widget.padding) == [10, 0, 10, 0]
            assert abs(second.handle.widget.y - (600 - 30 - 50)) <= 1, (
                first.handle.widget.pos, second.handle.widget.pos,
            )
            Window.size = (800, 600)
            Window.add_widget(root.handle.widget)
            try:
                for _ in range(15):
                    Clock.tick()
                assert renderer._sfle_resize_error is None, renderer._sfle_resize_error
                assert abs(first.handle.widget.height - 30) <= 1
                assert abs(second.handle.widget.height - 50) <= 1
                assert abs(button.handle.widget.height - 38) <= 1
                assert abs(button.handle.widget.font_size - 15) <= 0.01
                assert list(button.handle.widget.padding) == [10, 0, 10, 0]
                Window.dispatch("on_resize", 700, 500)
                for _ in range(15):
                    Clock.tick()
                assert renderer._sfle_resize_error is None, renderer._sfle_resize_error
                assert abs(first.handle.widget.height - 30) <= 1
                assert abs(second.handle.widget.height - 50) <= 1
            finally:
                Window.remove_widget(root.handle.widget)
                tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run([sys.executable, "-c", script], env=environment,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_simulated_retina_css_px_preserves_font_padding_and_height(self):
        """A 2x drawable viewport requires 2x native geometry, not 2x CSS units."""
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            # A deterministic 2x window/system ratio, independent of the
            # headless CI monitor's real physical density.
            scale = {"value": 2.0}
            KivyRenderer._read_css_pixel_scale = staticmethod(lambda: scale["value"])
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(800, True), AvailableSize(600, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh">
                    <button style="height:38px; font-size:15px; padding:0px 10px">Save</button>
                </div>
            """))
            button = root.children[0].handle.widget
            assert abs(button.height - 76) <= 1, button.size
            assert abs(button.font_size - 30) <= 0.01, button.font_size
            assert list(button.padding) == [20, 0, 20, 0], button.padding
            assert abs(root.handle.widget.height - 600) <= 1
            first_handle = root.children[0].handle
            # Simulate moving the same mounted window to a standard display,
            # then back to Retina. Native fonts and CSS paint must rescale
            # without replacing native widgets or changing authored CSS.
            scale["value"] = 1.0
            renderer.commit_layout(root)
            assert root.children[0].handle is first_handle
            assert abs(button.height - 38) <= 1, button.size
            assert abs(button.font_size - 15) <= 0.01, button.font_size
            assert list(button.padding) == [10, 0, 10, 0], button.padding
            scale["value"] = 2.0
            renderer.commit_layout(root)
            assert root.children[0].handle is first_handle
            assert abs(button.height - 76) <= 1, button.size
            assert abs(button.font_size - 30) <= 0.01, button.font_size
            assert list(button.padding) == [20, 0, 20, 0], button.padding
            tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_retina_nested_grid_dashboard_css_gap_padding_and_height(self):
        """A CSS GridItem flow must use the same drawable px as outer Cinnamon."""
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            KivyRenderer._read_css_pixel_scale = staticmethod(lambda: 2.0)
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(1600, True), AvailableSize(1200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh">
                    <Grid gap="16px">
                        <GridItem span="6">
                            <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
                                <button style="height:38px;font-size:15px;padding:0px 10px">Save</button>
                            </div>
                        </GridItem>
                        <GridItem span="6">
                            <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
                                <button style="height:38px;font-size:15px;padding:0px 10px">Cancel</button>
                            </div>
                        </GridItem>
                    </Grid>
                </div>
            """))
            grid = root.children[0]
            left, right = grid.children
            spacing = right.handle.widget.x - (
                left.handle.widget.x + left.handle.widget.width
            )
            assert abs(spacing - 32) <= 1, (
                spacing, left.handle.widget.pos, left.handle.widget.size,
                right.handle.widget.pos, right.handle.widget.size,
            )
            button = left.children[0].children[0].handle.widget
            assert abs(button.height - 76) <= 1, button.size
            assert abs(button.font_size - 30) < .01, button.font_size
            assert list(button.padding) == [20, 0, 20, 0], button.padding
            left_box = left.children[0].handle.widget
            # CSS card padding is 16 logical px = 32 native drawable px.
            assert abs(button.x - left_box.x - 32) <= 1, (
                button.pos, left_box.pos
            )
            assert button.y >= left_box.y
            tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_retina_dashboard_header_and_activity_dates_stay_inside_content(self):
        """Nested CSS Flex rows must preserve right-aligned trailing text."""
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            KivyRenderer._read_css_pixel_scale = staticmethod(lambda: 2.0)
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(1600, True), AvailableSize(1200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh">
                    <Grid gap="0px">
                        <GridItem span="2">
                            <div style="height:100vh;background:#1f2430;padding:20px 12px">
                                <h5 style="margin-left:8px">Mi panel</h5>
                            </div>
                        </GridItem>
                        <GridItem span="10">
                            <div style="height:100vh;background:white">
                                <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;padding:16px 20px">
                                    <p style="font-size:18px">Resumen</p>
                                    <p style="font-size:15px">Hola, Fredo</p>
                                </div>
                                <div style="padding:16px">
                                    <div style="padding:16px;border:1px solid #e0e0e0">
                                        <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;gap:10px;padding:16px 20px">
                                            <p style="width:100%;font-size:14px">Ana López creó un reporte</p>
                                            <p style="min-width:120px;font-size:14px;text-align:right">23 de Octubre</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </GridItem>
                    </Grid>
                </div>
            """))
            content = root.children[0].children[1].children[0]
            header = content.children[0]
            title, greeting = header.children
            rect = lambda mounted: mounted.handle.widget
            assert rect(greeting).right <= rect(header).right + 1, (
                rect(greeting).pos, rect(greeting).size,
                rect(header).pos, rect(header).size,
            )
            assert rect(greeting).x > rect(title).right
            row = content.children[1].children[0].children[0]
            description, date = row.children
            assert rect(date).right <= rect(row).right + 1, (
                rect(date).pos, rect(date).size,
                rect(row).pos, rect(row).size,
            )
            assert rect(date).x >= rect(description).right - 1, (
                rect(date).pos, rect(description).pos, rect(description).size,
            )
            tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_retina_sidebar_buttons_use_css_height_spacing_and_padding(self):
        """CSS sidebar gaps and 38px button boxes must survive nested Grid."""
        script = textwrap.dedent(r'''
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            KivyRenderer._read_css_pixel_scale = staticmethod(lambda: 2.0)
            renderer = KivyRenderer(sfle_constraints=LayoutConstraints(
                AvailableSize(1600, True), AvailableSize(1200, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh">
                    <Grid gap="0px">
                        <GridItem span="2">
                            <div style="height:100vh;background:#1f2430;padding:20px 12px;display:flex;flex-direction:column;gap:20px">
                                <h5 style="margin-left:8px">Mi panel</h5>
                                <div style="display:flex;flex-direction:column;gap:10px">
                                    <button style="height:38px;font-size:15px;padding:0px 10px;background:#3b6ef5;color:white;text-align:left">Resumen</button>
                                    <button style="height:38px;font-size:15px;padding:0px 10px;color:#6b7385;text-align:left">Usuarios</button>
                                    <button style="height:38px;font-size:15px;padding:0px 10px;color:#6b7385;text-align:left">Reportes</button>
                                </div>
                            </div>
                        </GridItem>
                    </Grid>
                </div>
            """))
            sidebar = root.children[0].children[0].children[0]
            nav = sidebar.children[1]
            buttons = [item.handle.widget for item in nav.children]
            assert len(buttons) == 3
            for item in buttons:
                assert abs(item.height - 76) <= 1, (item.pos, item.size)
            for first, second in zip(buttons, buttons[1:]):
                gap = first.y - (second.y + second.height)
                assert abs(gap - 20) <= 1, (gap, first.pos, second.pos)
            assert all(abs(item.x - (sidebar.handle.widget.x + 24)) <= 1
                       for item in buttons), [item.pos for item in buttons]
            assert buttons[1].background_normal == ""
            assert buttons[1]._psx_css_button_background[2].rgba[3] == 0
            tree.unmount()
        ''')
        environment = dict(os.environ, KIVY_NO_FILELOG="1", KIVY_NO_ARGS="1")
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_two_grid_items_fill_row_with_unrestricted_auto_span(self):
        script = textwrap.dedent(r'''
            import os
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.core.window import Window
            from kivy.clock import Clock
            from psx import psx
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.backend import load_layout_engine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            engine = (load_layout_engine()
                      if os.getenv("PSX_KIVY_LAYOUT_ENGINE") == "rust"
                      else PythonLayoutEngine())
            if os.getenv("PSX_KIVY_LAYOUT_ENGINE") == "rust":
                assert engine.backend_name == "rust"
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(1200, True), AvailableSize(600, True)),
                engine=engine,
            )
            tree = Reconciler(renderer)
            root = tree.render(psx("""
                <div style="height:100vh; background:red">
                    <Grid gap="0px">
                        <GridItem span="2"><p>Sidebar</p></GridItem>
                        <GridItem><p>Content</p></GridItem>
                    </Grid>
                </div>
            """))
            grid = root.children[0]
            left, right = grid.children
            def geometry(node):
                w = node.handle.widget
                return tuple(w.pos), tuple(w.size)
            print("GRID_RECTS", geometry(root), geometry(grid),
                  geometry(left), geometry(right), flush=True)
            assert grid.handle.widget.width == 1200
            assert abs(left.handle.widget.width - 200) <= 1
            assert abs(right.handle.widget.width - 1000) <= 1
            assert abs(right.handle.widget.x - 200) <= 1
            assert abs(right.handle.widget.x + right.handle.widget.width - 1200) <= 1
            Window.size = (1200, 600)
            Window.add_widget(root.handle.widget)
            Clock.tick()
            Clock.tick()
            for expected_x, item in ((0, left), (200, right)):
                # Kivy canvas positions are in window coordinates: a native
                # Label at (0,0) paints bottom-left even if its parent is
                # placed at y=581. A summed ancestor offset is NOT evidence
                # that the native text is actually top-aligned.
                paragraph = item.children[0].handle.widget
                label = item.children[0].children[0].handle.widget
                for widget in (item.handle.widget, paragraph, label):
                    print("NATIVE_WIDGET_RECT", tuple(widget.pos),
                          tuple(widget.size), flush=True)
                    assert abs(widget.x - expected_x) <= 1, (
                        expected_x, tuple(widget.pos))
                    assert widget.y >= 550, tuple(widget.pos)
            Window.remove_widget(root.handle.widget)
            tree.unmount()
        ''')
        environment = dict(os.environ)
        environment["KIVY_NO_FILELOG"] = "1"
        environment.pop("KIVY_NO_CONSOLELOG", None)
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run([sys.executable, "-c", script],
                                env=environment, capture_output=True,
                                text=True, timeout=90)
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

            from psx import Flex, Text, Button, Checkbox, Slider, Spacer, component, use_state, psx
            from psx.core.native import Native
            from psx.core.vnode import create_element
            from psx.sfle.external_native_geometry_ports import SFLEExternalPort
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
                      padding="10" align_items="flex-start">
                    <Flex direction="row" width="120px" height="40px"
                          gap="6" align_items="flex-start">
                        <Button label="A" key="a" layout_width="30px"
                                layout_height="15px" flex_basis="30px"
                                flex_shrink="0" />
                        <Button label="B" key="b" layout_width="20px"
                                layout_height="15px" flex_basis="20px"
                                flex_shrink="0" />
                    </Flex>
                </Flex>
            '''))
            nested = root.children[0].handle.widget
            a, b = [i.handle.widget for i in root.children[0].children]
            assert type(nested) is Widget and not isinstance(nested, BoxLayout)
            assert nested.parent is root.handle.widget
            assert (nested.x, nested.y, nested.width, nested.height) == (10, 30, 120, 40), tuple(nested.pos) + tuple(nested.size)
            # Kivy native canvases do not inherit a parent's translation.
            # The nested Flex is at (10, 30) and must paint its children
            # in window-space, not at detached parent-relative (0, 25).
            assert (a.x, a.y, a.width, a.height) == (10, 55, 30, 15)
            assert (b.x, b.y, b.width, b.height) == (46, 55, 20, 15)
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
            assert tuple(external_widget.pos) + tuple(external_widget.size) == (0, 68, 26, 12)
            assert "measure" in external_calls
            assert ("apply", Rect(0, 68, 26, 12)) in external_calls
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

            from psx.core.native import NativeWidget
            from psx.core.vnode import native_widget
            native_created = []
            backend, tree = create()
            def bad_native_factory():
                native_created.append(True)
                return Widget()
            try:
                tree.render(Flex(
                    native_widget(NativeWidget(renderer="kivy", factory=bad_native_factory),
                                  layout_width="20px", layout_height="20px"),
                    width="160px", height="80px",
                ))
            except RendererCapabilityError as error:
                assert "Native requires" in str(error)
            else:
                raise AssertionError("Kivy Native without SFLE port was mounted")
            assert not native_created
            tree.unmount()

            # Retired layout primitives are never registered or routed natively.
            from psx.core.registry import builtin_component_registry
            registry = builtin_component_registry()
            assert not registry.contains("Row")
            assert not registry.contains("Column")
            backend, tree = create()
            assert backend.adapters.get("Row") is None
            assert backend.adapters.get("Column") is None
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
                assert "Native SFLE SFLE geometry" in str(error)
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
            from kivy.clock import Clock
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import (Text, Button, Input, Checkbox, TextArea, Slider,
                             Spacer, Divider, Image, ProgressBar, Radio,
                             RadioGroup, Select, Switch, Link, Badge, SpinBox,
                             Scroll, Flex)
            from psx.core.vnode import Box
            from psx.core.vnode import create_element
            from psx.core.errors import RendererCapabilityError
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
            from psx.sfle.native_operation_oracles import Observation, ORACLES

            with TemporaryDirectory() as tmp:
                import struct
                import zlib
                def chunk(kind, data):
                    return (struct.pack(">I", len(data)) + kind + data
                            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
                image_bytes = (
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">2I5B", 2, 2, 8, 6, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff\x33\x66\xff" * 2) * 2))
                    + chunk(b"IEND", b"")
                )
                path = Path(tmp) / "pixel.png"
                path.write_bytes(image_bytes)
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
                native = set(NATIVE_LEAF_TYPES["kivy"]) | {"Flex"}
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
                        assert (native_widget.width == 60 if name != "Box" else native_widget.width > 0), (name, native_widget.size)
                        assert (native_widget.height == 24 if name != "Box" else native_widget.height > 0), (name, native_widget.size)
                        before_rectangle = (*native_widget.pos, *native_widget.size)
                        prior_order = tuple(child.node.key for child in first.children)
                        before_state = (
                            before_rectangle,
                            tuple(dict(child.node.props) for child in old.children),
                        )
                        before_observation = Observation(
                            native_identity=id(native_widget), mounted=True,
                            rect=before_rectangle, state=before_state,
                            order=prior_order,
                        )
                        ORACLES["create"](None, before_observation)
                        second = tree.render(view(name, 80, True))
                        current = second.children[1]
                        unchanged_peer = second.children[0].handle.widget
                        assert id(unchanged_peer) not in renderer._sfle_native_intrinsic_cache.last_measured, name
                        assert current is old, name
                        assert current.handle.widget is native_widget, name
                        assert (native_widget.width == 80 if name != "Box" else native_widget.width > 0), (name, native_widget.size)
                        assert native_widget.x > second.children[0].handle.widget.x, name
                        after_rectangle = (*native_widget.pos, *native_widget.size)
                        current_state = (
                            after_rectangle,
                            tuple(dict(child.node.props) for child in old.children),
                        )
                        after_observation = Observation(
                            native_identity=id(native_widget), mounted=True,
                            rect=after_rectangle, state=current_state,
                            order=tuple(child.node.key for child in second.children),
                        )
                        ORACLES["update"](before_observation, after_observation)
                        ORACLES["reorder"](before_observation, after_observation)
                        # C5: each registered native family must re-commit
                        # without replacing its Kivy widget.
                        for reason in ("content", "font", "theme", "resource", "dpi", "viewport"):
                            measured_generation = renderer.sfle_result.generation
                            renderer.request_sfle_invalidation(reason)
                            Clock.tick()
                            assert renderer.sfle_result.generation > measured_generation, (name, reason)
                            assert current.handle.widget is native_widget, (name, reason)
                            assert not renderer._sfle_measurement_invalidations.pending, (name, reason)
                        if name == "Image":
                            import os
                            original_stamp = path.stat().st_mtime_ns
                            os.utime(path, ns=(
                                original_stamp + 1_000_000_000,
                                original_stamp + 1_000_000_000))
                            previous = renderer.sfle_result.generation
                            renderer._sfle_poll_image_resources(
                                renderer._sfle_invalidation_lifetime)
                            Clock.tick()
                            assert renderer.sfle_result.generation > previous, name
                            assert current.handle.widget is native_widget, name
                        attempted = view(name, 80, True)
                        current_node = attempted.children[1]
                        from dataclasses import replace
                        from types import MappingProxyType
                        invalid = replace(
                            current_node, props=MappingProxyType({
                                **dict(current_node.props), "on_invalid": 1,
                            }),
                        )
                        forged = replace(
                            attempted, children=(attempted.children[0], invalid),
                        )
                        before_pos = tuple(native_widget.pos)
                        before_size = tuple(native_widget.size)
                        try:
                            tree.render(forged)
                        except (TypeError, RendererCapabilityError):
                            pass
                        else:
                            raise AssertionError("Malformed native callback was accepted")
                        assert current.handle.widget is native_widget, name
                        assert tuple(native_widget.pos) == before_pos, name
                        assert tuple(native_widget.size) == before_size, name
                        ORACLES["rollback"](
                            after_observation, Observation(
                                native_identity=id(native_widget), mounted=True,
                                rect=after_rectangle, state=current_state,
                                order=after_observation.order, mutation_failed=True,
                            ),
                        )
                        tree.render(Flex(
                            Button("Peer", key="peer", layout_width="20px",
                                   layout_height="24px"),
                            width=260, height=90, align_items="flex-start"))
                        assert old.disposed, name
                        assert native_widget.parent is None, name
                        ORACLES["unmount"](
                            after_observation, Observation(
                                native_identity=id(native_widget), mounted=False,
                                rect=after_rectangle, state=current_state,
                                disposed=True,
                            ),
                        )
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
            from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
            from psx.sfle.native_operation_contracts import EVENTLESS

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
            assert set(callbacks) == (set(NATIVE_LEAF_TYPES["kivy"]) | {"Flex"}) - EVENTLESS
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

    def test_borrowed_native_widget_restores_parent_and_disposes_only_own_bindings(self):
        """Borrowed Kivy Native preserves caller ownership and parent."""
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.widget import Widget
            from psx import Flex
            from psx.core.native import NativeWidget, NativeOwnership
            from psx.core.vnode import native_widget
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.external_native_geometry_ports import SFLEExternalPort
            from psx.sfle.native_operation_oracles import Observation, ORACLES
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes, Rect

            caller_parent = Widget()
            widget = Widget()
            widget.size_hint = (0.5, 0.75)
            widget.pos_hint = {"center_x": 0.5}
            original_size_hint = tuple(widget.size_hint)
            original_pos_hint = dict(widget.pos_hint)
            caller_parent.add_widget(widget)
            calls = []
            def measure(w, c):
                calls.append("measure")
                return IntrinsicSizes(10, 45, 10, 20, 45, 20)
            def apply(w, rect):
                calls.append("apply")
                w.pos = (rect.x, rect.y)
                w.size = (rect.width, rect.height)
            def read(w):
                calls.append("read")
                return Rect(w.x, w.y, w.width, w.height)
            declaration = NativeWidget(
                renderer="kivy", widget=widget,
                ownership=NativeOwnership.BORROWED,
                sfle_port=SFLEExternalPort(measure, apply, read),
            )
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            def view(width):
                return Flex(native_widget(
                    declaration, key="borrowed",
                    layout_width=f"{width}px", layout_height="20px",
                    flex_basis=f"{width}px", flex_shrink=0),
                    width=160, height=80, align_items="flex-start")
            first = tree.render(view(35))
            assert first.children[0].handle.widget is widget
            assert widget.parent is not caller_parent
            second = tree.render(view(45))
            assert second.children[0].handle.widget is widget
            before = Observation(id(widget), True, (widget.x, widget.y, 45, 20),
                                 owner="caller")
            tree.unmount()
            after = Observation(id(widget), False, (widget.x, widget.y, 45, 20),
                                owner="caller", disposed=False)
            ORACLES["borrowed_ownership"](before, after)
            assert widget.parent is caller_parent
            assert widget in caller_parent.children
            assert tuple(widget.size_hint) == original_size_hint
            assert dict(widget.pos_hint) == original_pos_hint
            assert {"measure", "apply", "read"} <= set(calls)
            caller_parent.remove_widget(widget)
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run(
            [sys.executable, "-c", script], env=env,
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_external_ownership_owned_native_and_custom_adapter_cleanup(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.widget import Widget
            from psx import Flex
            from psx.core.native import NativeWidget
            from psx.core.vnode import native_widget, create_element
            from psx.core.reconcile import Reconciler
            from psx.core.errors import RendererCapabilityError
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.sfle.external_native_geometry_ports import SFLEExternalPort
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes, Rect

            def port():
                def measure(w, c):
                    return IntrinsicSizes(10, 40, 10, 18, 40, 18)
                def apply(w, r):
                    w.pos = (r.x, r.y)
                    w.size = (r.width, r.height)
                def read(w):
                    return Rect(w.x, w.y, w.width, w.height)
                return SFLEExternalPort(measure, apply, read)
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine())
            tree = Reconciler(renderer)
            created = []
            def factory():
                w = Widget(size_hint=(None, None))
                created.append(w)
                return w
            owned = NativeWidget(renderer="kivy", factory=factory,
                                 sfle_port=port())
            root = tree.render(Flex(
                native_widget(owned, key="owned",
                              layout_width="40px", layout_height="18px",
                              flex_basis="40px", flex_shrink=0),
                width=160, height=80,
            ))
            assert root.children[0].handle.widget is created[0]
            assert created[0].parent is root.handle.widget
            tree.unmount()
            assert created[0].parent is None

            released = []
            class CustomAdapter:
                sfle_port = port()
                def create(self, backend, node, parent):
                    return KivyHandle("ExternalTile",
                                      Widget(size_hint=(None, None)), {})
                def update(self, backend, handle, changed, removed):
                    pass
                def destroy(self, backend, handle):
                    released.append(handle.widget)
                    if handle.widget.parent is not None:
                        handle.widget.parent.remove_widget(handle.widget)
                def bind_event(self, backend, handle, event, slot):
                    raise RendererCapabilityError("Unsupported custom event")
                def unbind_event(self, backend, subscription):
                    pass
            renderer.register_adapter("ExternalTile", CustomAdapter())
            root = tree.render(Flex(
                create_element("ExternalTile", key="custom",
                               layout_width="35px", layout_height="18px",
                               flex_basis="35px", flex_shrink=0),
                width=160, height=80,
            ))
            custom = root.children[0].handle.widget
            assert custom.parent is root.handle.widget
            tree.unmount()
            assert released == [custom]
            assert custom.parent is None
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run(
            [sys.executable, "-c", script], env=env,
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_borrowed_kivy_event_subscriptions_are_removed_on_unmount(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.widget import Widget
            from psx import Flex
            from psx.core.native import NativeWidget, NativeOwnership
            from psx.core.vnode import native_widget
            from psx.core.reconcile import Reconciler
            from psx.sfle.external_native_geometry_ports import SFLEExternalPort
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes, Rect

            widget = Widget()
            caller = Widget()
            caller.add_widget(widget)
            def port():
                return SFLEExternalPort(
                    lambda w, c: IntrinsicSizes(10, 40, 10, 20, 40, 20),
                    lambda w, rect: (
                        setattr(w, "pos", (rect.x, rect.y)),
                        setattr(w, "size", (rect.width, rect.height))),
                    lambda w: Rect(w.x, w.y, w.width, w.height))
            declaration = NativeWidget(
                renderer="kivy", widget=widget,
                ownership=NativeOwnership.BORROWED, sfle_port=port(),
                bind_event=lambda w, event, slot: bind_native(w, event, slot),
            )
            def bind_native(w, event, slot):
                assert event == "on_native_signal:pos"
                callback = lambda *_: slot.invoke()
                w.bind(pos=callback)
                return lambda: w.unbind(pos=callback)
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine())
            reconciler = Reconciler(renderer)
            calls = []
            def view(callback):
                return Flex(native_widget(
                    declaration, key="case", **{
                        "on_native_signal:pos": callback,
                        "layout_width": "40px", "layout_height": "20px",
                        "flex_basis": "40px", "flex_shrink": 0,
                    }),
                    width=160, height=80, align_items="flex-start")
            root = reconciler.render(view(lambda: calls.append("old")))
            assert root.children[0].handle.widget is widget
            before = len(calls)
            widget.pos = (7, 9)
            assert calls[before:] == ["old"], calls
            root = reconciler.render(view(lambda: calls.append("new")))
            assert root.children[0].handle.widget is widget
            before = len(calls)
            widget.pos = (8, 10)
            assert calls[before:] == ["new"], calls
            reconciler.unmount()
            assert widget.parent is caller
            before = len(calls)
            widget.pos = (9, 11)
            assert len(calls) == before
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_semantic_measurement_invalidations_do_not_remount_kivy(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from psx import Flex, Text
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine())
            reconciler = Reconciler(renderer)
            for reason in ("content", "font", "theme", "resource", "dpi", "viewport"):
                reconciler.unmount()
                root = reconciler.render(Flex(
                    Text("Stable", key="fixed", layout_width="50px",
                         layout_height="20px"),
                    width=160, height=80, align_items="flex-start"))
                native = root.children[0].handle.widget
                generation = renderer.sfle_result.generation
                renderer.request_sfle_invalidation(reason)
                renderer.request_sfle_invalidation(reason)
                Clock.tick()
                assert root.children[0].handle.widget is native, reason
                assert renderer.sfle_result.generation == generation + 1, reason
                assert not renderer._sfle_measurement_invalidations.pending, reason
            reconciler.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True,
                                timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)



    def test_kivy_readback_race_rolls_back_real_widget_geometry(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.errors import SFLEError
            from psx.sfle.model import AvailableSize, LayoutConstraints
            import psx.sfle.kivy_layout_bridge as bridge

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Button("First", key="first", layout_width="40px", layout_height="20px"),
                Button("Second", key="second", layout_width="30px", layout_height="20px"),
                width=160, height=80, gap=8, align_items="flex-start",
            ))
            widgets = tuple(child.handle.widget for child in root.children)
            before = tuple((tuple(w.pos), tuple(w.size)) for w in widgets)
            published = renderer.sfle_result
            original_error = bridge.DevicePixelSpace.error
            injected = {"done": False}

            def readback_error(space, expected, observed):
                if not injected["done"]:
                    injected["done"] = True
                    renderer._sfle_measurement_invalidations.request("resource")
                return original_error(space, expected, observed)

            with patch.object(bridge.DevicePixelSpace, "error", readback_error):
                renderer.commit_layout(root)
            assert injected["done"]
            assert tuple((tuple(w.pos), tuple(w.size)) for w in widgets) == before
            assert renderer.sfle_result.generation >= published.generation + 2
            assert not renderer._sfle_measurement_invalidations.pending
            assert not renderer._sfle_measurement_invalidations.pending
            assert tuple(child.handle.widget for child in root.children) == widgets
            tree.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


    def test_kivy_native_geometry_write_failure_restores_previous_rectangles(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            import psx.sfle.kivy_layout_bridge as bridge

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Button("First", key="first", layout_width="40px", layout_height="20px"),
                Button("Second", key="second", layout_width="30px", layout_height="20px"),
                width=160, height=80, gap=8, align_items="flex-start",
            ))
            widgets = tuple(child.handle.widget for child in root.children)
            before = tuple((tuple(w.pos), tuple(w.size)) for w in widgets)
            published = renderer.sfle_result
            original_committer = bridge.NativeGeometryCommitter

            def interrupted_committer(*args, **kwargs):
                apply = original_committer(*args, **kwargs)
                def fail_after_application(result):
                    apply(result)
                    widgets[0].pos = (7, 9)
                    widgets[0].size = (13, 15)
                    raise RuntimeError("injected Kivy native application failure")
                return fail_after_application

            with patch.object(bridge, "NativeGeometryCommitter", side_effect=interrupted_committer):
                try:
                    renderer.commit_layout(root)
                except RuntimeError as exc:
                    assert "injected Kivy native application failure" in str(exc)
                else:
                    raise AssertionError("Kivy native application unexpectedly succeeded")
            assert tuple((tuple(w.pos), tuple(w.size)) for w in widgets) == before
            assert renderer.sfle_result is published
            renderer.commit_layout(root)
            assert tuple(child.handle.widget for child in root.children) == widgets
            tree.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)

    def test_kivy_invalidation_during_native_application_rolls_back(self):
        script = textwrap.dedent(r"""
            from unittest.mock import patch
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Button, Flex
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            import psx.sfle.kivy_layout_bridge as bridge

            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(160, True), AvailableSize(80, True)),
                engine=PythonLayoutEngine(),
            )
            tree = Reconciler(renderer)
            root = tree.render(Flex(
                Button("First", key="first", layout_width="40px", layout_height="20px"),
                Button("Second", key="second", layout_width="30px", layout_height="20px"),
                width=160, height=80, gap=8, align_items="flex-start",
            ))
            widgets = tuple(child.handle.widget for child in root.children)
            before = tuple((tuple(w.pos), tuple(w.size)) for w in widgets)
            published = renderer.sfle_result
            original_committer = bridge.NativeGeometryCommitter
            injected = {"done": False}

            def interrupted_committer(*args, **kwargs):
                apply = original_committer(*args, **kwargs)
                def fail_after_application(result):
                    apply(result)
                    if not injected["done"]:
                        injected["done"] = True
                        renderer._sfle_measurement_invalidations.request("dpi")
                return fail_after_application

            with patch.object(bridge, "NativeGeometryCommitter", side_effect=interrupted_committer):
                renderer.commit_layout(root)
            assert injected["done"]
            assert tuple((tuple(w.pos), tuple(w.size)) for w in widgets) == before
            assert renderer.sfle_result.generation >= published.generation + 2
            assert not renderer._sfle_measurement_invalidations.pending
            assert tuple(child.handle.widget for child in root.children) == widgets
            tree.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


    def test_live_kivy_image_file_revision_reflows_native_siblings(self):
        script = textwrap.dedent(r"""
            import struct
            import tempfile
            import zlib
            from pathlib import Path
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from psx import Flex, Image, Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints

            def write_png(path, width, height):
                def chunk(kind, value):
                    return (struct.pack(">I", len(value)) + kind + value
                            + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff))
                row = b"\x00" + b"\xff\x33\x66\xff" * width
                Path(path).write_bytes(
                    b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(row * height))
                    + chunk(b"IEND", b"")
                )

            limits = LayoutConstraints(AvailableSize(160, True), AvailableSize(80, True))
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "revision.png"
                write_png(path, 24, 12)
                renderer = KivyRenderer(sfle_constraints=limits, engine=PythonLayoutEngine())
                reconciler = Reconciler(renderer)
                root = reconciler.render(Flex(
                    Image(str(path), key="picture", fit="contain"),
                    Button("Peer", key="peer", layout_width="30px", layout_height="20px"),
                    direction="column", width=160, height=80, align_items="flex-start",
                ))
                image = root.children[0].handle.widget
                peer = root.children[1].handle.widget
                before = renderer.sfle_result.generation
                assert image.height == 12
                write_png(path, 24, 24)
                renderer._sfle_poll_image_resources(renderer._sfle_invalidation_lifetime)
                Clock.tick()
                assert root.children[0].handle.widget is image
                assert root.children[1].handle.widget is peer
                assert renderer.sfle_result.generation > before
                assert abs(image.height - 24) <= 1, image.height
                assert not renderer._sfle_measurement_invalidations.pending
                assert not renderer._sfle_image_resource_watch.changed()
                reconciler.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


    def test_targeted_kivy_resource_remeasurement_skips_native_peer(self):
        script = textwrap.dedent(r"""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from psx import Button, Flex
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
            root = tree.render(Flex(
                Button("First", key="first", layout_width="40px", layout_height="20px"),
                Button("Second", key="second", layout_width="30px", layout_height="20px"),
                width=160, height=80, gap=8, align_items="flex-start",
            ))
            first, second = (child.handle.widget for child in root.children)
            baseline = tuple((tuple(widget.pos), tuple(widget.size)) for widget in (first, second))
            renderer.request_sfle_invalidation("resource", widget_id=id(first))
            Clock.tick()
            cache = renderer._sfle_native_intrinsic_cache
            assert id(first) in cache.last_measured
            assert id(second) not in cache.last_measured
            assert tuple((tuple(widget.pos), tuple(widget.size)) for widget in (first, second)) == baseline
            assert root.children[0].handle.widget is first
            assert root.children[1].handle.widget is second
            tree.unmount()
        """)
        env = dict(os.environ)
        env["KIVY_NO_ARGS"] = "1"
        env["KIVY_NO_FILELOG"] = "1"
        env.pop("KIVY_NO_CONSOLELOG", None)
        result = subprocess.run([sys.executable, "-c", script],
                                env=env, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


def test_html_flow_public_native_geometry_receipt_kivy(request):
    from tests.certification.public_behavior_census import Feature, assert_feature
    script = textwrap.dedent("""
        from kivy.config import Config
        Config.set("graphics", "window_state", "hidden")
        from psx import psx
        from psx.core.reconcile import Reconciler
        from psx.renderers.kivy.kivy import KivyRenderer
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, LayoutConstraints

        renderer = KivyRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(220, True), AvailableSize(120, True)),
            engine=PythonLayoutEngine(),
        )
        reconciler = Reconciler(renderer)
        root = reconciler.render(
            psx("<div><button>First</button><button>Second</button></div>")
        )
        first, second = (child.handle.widget for child in root.children)
        assert 0 < round(first.width) < 220
        assert 0 < round(second.width) < 220
        assert round(first.y) == round(second.y)
        assert round(second.x) == round(first.x + first.width)
        assert first.parent is root.handle.widget
        assert renderer.sfle_result.geometry_commit_error <= 1
        reconciler.unmount()
        assert first.parent is None and second.parent is None
    """)
    environment = dict(os.environ)
    environment["KIVY_NO_FILELOG"] = "1"
    environment["KIVY_NO_ARGS"] = "1"
    environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
    run = subprocess.run(
        [sys.executable, "-c", script], env=environment,
        capture_output=True, text=True, timeout=90,
    )
    assert_feature(
        request, Feature("div", "kivy", "interaction", "semantic_flow",
                         "native_geometry", applicability="partial_native"),
        run.returncode == 0,
        run.stdout + "\\n" + run.stderr,
    )
