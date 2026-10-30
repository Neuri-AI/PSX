from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivyRendererSubprocessTests(unittest.TestCase):

    def test_css_px_font_matches_cinnamon_at_all_density_settings(self) -> None:
        """CSS px lengths must match Cinnamon geometry rather than Kivy sp."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.metrics import Metrics
            from kivy.uix.label import Label
            from psx.renderers.components.text import apply_kivy_text
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle

            renderer = KivyRenderer()
            original_density = Metrics.density
            original_fontscale = Metrics.fontscale
            try:
                for density in (1., 1.5, 2.):
                    Metrics.density = density
                    Metrics.fontscale = 1.
                    widget = Label()
                    apply_kivy_text(widget, {"value": "Hello", "font_size": 14})
                    assert abs(widget.font_size - 14) < 0.01
                    # CSS font-size and line-height use one canonical logical px space;
                    # the dimensionless line_height remains stable.
                    handle = KivyHandle("Text", widget, {"value": "Hello"})
                    style = resolve_style(
                        parse_stylesheet("p {font-size: 16px; line-height: 24px}"),
                        StyleTarget("p"),
                    )
                    renderer.apply_css(handle, style)
                    assert abs(widget.font_size - 16) < 0.01
                    assert abs(widget.line_height - 1.5) < 0.01
            finally:
                Metrics.density = original_density
                Metrics.fontscale = original_fontscale
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        if "Unable to get a Window" in result.stderr:
            self.skipTest("No usable Kivy window provider.")
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_nested_window_resize_event_does_not_recurse(self) -> None:
        """SDL2/Cocoa synchronous property dispatch must not loop on resize."""
        script = textwrap.dedent("""
            from psx.renderers.kivy.kivy import KivyRenderer

            renderer = object.__new__(KivyRenderer)
            window = object()
            class Root:
                parent = window
                def __init__(self):
                    self._size = (200, 150)
                    self.writes = 0
                @property
                def size(self):
                    return self._size
                @size.setter
                def size(self, size):
                    self.writes += 1
                    self._size = tuple(size)
                    # Emulate a nested event callback while a native property
                    # write is still active, with provider-adjusted dimensions.
                    renderer._sfle_on_window_resize(window, size[0] + 1, size[1] + 1)
            root = Root()
            renderer._sfle_watched_widget = root
            renderer._sfle_on_window_resize(window, 800, 600)
            assert root.size == (800, 600)
            assert root.writes == 1
            renderer._sfle_on_window_resize(window, 800, 600)
            assert root.writes == 1
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run([sys.executable, "-c", script],
                                env=environment, capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_retina_resize_prefers_drawable_window_over_system_event_size(self) -> None:
        script = textwrap.dedent("""
            from psx.renderers.kivy.kivy import KivyRenderer

            renderer = object.__new__(KivyRenderer)
            class Window:
                size = (1600, 1200)
                system_size = (800, 600)
            window = Window()
            class Root:
                parent = window
                size = (800, 600)
            root = Root()
            renderer._sfle_watched_widget = root
            renderer._sfle_on_window_resize(window, 800, 600)
            assert root.size == (1600, 1200), root.size
            # Repeated Cocoa event with unchanged drawable dimensions must
            # not resize the root or reenter the SFLE transaction.
            renderer._sfle_on_window_resize(window, 800, 600)
            assert root.size == (1600, 1200), root.size
        """)
        environment = dict(os.environ)
        environment["KIVY_NO_ARGS"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_input_and_textarea_css_background_survives_focus_and_resets(self):
        """CSS paint must replace both TextInput skin states without remount."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style
            from kivy.uix.textinput import TextInput

            renderer = KivyRenderer()
            for component in ("Input", "TextArea"):
                widget = TextInput(multiline=component == "TextArea")
                handle = KivyHandle(component, widget, {})
                original = (widget.background_normal,
                            widget.background_active,
                            tuple(widget.background_color))
                def style(value):
                    return resolve_style(
                        parse_stylesheet("input {" + value + "}"),
                        StyleTarget("input"),
                    )
                renderer.apply_css(handle, style(
                    "background-color: #123456; border-radius: 8px;"
                ))
                painted = widget._psx_css_input_background
                assert widget.background_normal == ""
                assert widget.background_active == ""
                assert tuple(widget.background_color) == (0, 0, 0, 0)
                assert all(abs(a - b) < 1e-5 for a, b in zip(\n                    painted[2].rgba[:3], (18/255, 52/255, 86/255)))
                widget.focus = True
                assert widget._psx_css_input_background is painted
                renderer.apply_css(handle, style(
                    "background-color: #abcdef; border-radius: 12px;"
                ))
                assert widget._psx_css_input_background is painted
                assert painted[3].radius
                renderer.apply_css(handle, style(""))
                assert not hasattr(widget, "_psx_css_input_background")
                assert (widget.background_normal,
                        widget.background_active,
                        tuple(widget.background_color)) == original
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_select_and_link_background_styles_own_and_restore_native_skins(self):
        """Spinners and links use authored backgrounds without theme bleed."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.spinner import Spinner
            from kivy.uix.button import Button
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.cascade import StyleTarget, resolve_style
            from psx.css.parser import parse_stylesheet

            renderer = KivyRenderer()
            for node_type, widget in (("Select", Spinner()), ("Link", Button())):
                handle = KivyHandle(node_type, widget, {})
                original = (widget.background_normal, widget.background_down,
                            tuple(widget.background_color))
                styled = resolve_style(parse_stylesheet(
                    "button {background-color:#123456; border-radius:8px}"),
                    StyleTarget("button"))
                empty = resolve_style(parse_stylesheet(""), StyleTarget("button"))
                renderer.apply_css(handle, styled)
                painted = widget._psx_css_button_background
                assert widget.background_normal == ""
                assert widget.background_down == ""
                assert tuple(widget.background_color) == (0, 0, 0, 0)
                assert painted[2].rgba[0] > 0
                renderer.apply_css(handle, styled)
                assert widget._psx_css_button_background is painted
                renderer.apply_css(handle, empty)
                assert not hasattr(widget, "_psx_css_button_background")
                assert (widget.background_normal, widget.background_down,
                        tuple(widget.background_color)) == original
        """)
        result = subprocess.run([sys.executable, "-c", script],
                                env=environment, capture_output=True,
                                text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_checkbox_and_radio_authored_surfaces_preserve_native_indicators(self):
        """CSS host paint must not replace checkbox/radio selection state."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.checkbox import CheckBox
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.label import Label
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.cascade import StyleTarget, resolve_style
            from psx.css.parser import parse_stylesheet

            def style(text):
                return resolve_style(
                    parse_stylesheet("div {" + text + "}"),
                    StyleTarget("div"),
                )
            renderer = KivyRenderer()
            checked = CheckBox()
            checked.active = True
            radio = BoxLayout()
            radio._psx_label = Label()
            for name, widget in (("Checkbox", checked), ("Radio", radio)):
                initial = checked.active
                handle = KivyHandle(name, widget, {})
                renderer.apply_css(handle, style(
                    "background-color:#123456; border-radius:8px"
                ))
                painted = widget._psx_css_check_background
                assert painted[2].rgba[0] > 0
                assert painted[0] in widget.canvas.before.children
                renderer.apply_css(handle, style(
                    "background-color:#abcdef; border-radius:12px"
                ))
                assert widget._psx_css_check_background is painted
                renderer.apply_css(handle, style(""))
                assert not hasattr(widget, "_psx_css_check_background")
                assert painted[0] not in widget.canvas.before.children
                assert checked.active == initial
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_uniform_border_has_exactly_one_paint_path_on_retina(self):
        """Never overpaint a uniform border with four duplicate side lines."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.uix.button import Button
            from kivy.uix.widget import Widget
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style

            renderer = KivyRenderer()
            renderer._psx_css_pixel_scale = 2.0
            for node_type, widget in (("Button", Button()), ("div", Widget())):
                style = resolve_style(
                    parse_stylesheet(
                        "div { border: 2px solid #364152; border-radius: 8px; }"
                    ), StyleTarget("div"),
                )
                handle = KivyHandle(node_type, widget, {})
                renderer.apply_css(handle, style)
                border = (widget._psx_css_control_stroke if node_type == "Button"
                          else widget._psx_css_stroke)
                assert abs(border[3].width - 4) < 0.01
                assert not hasattr(widget, "_psx_css_control_side_strokes")
                assert not hasattr(widget, "_psx_css_side_strokes")
                renderer.apply_css(handle, None)
                assert not hasattr(widget, "_psx_css_control_stroke")
                assert not hasattr(widget, "_psx_css_stroke")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_control_css_side_borders_keep_untouched_edges_transparent(self):
        """Native Kivy sides follow Qt/QSS authored per-edge semantics."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.button import Button
            from kivy.uix.spinner import Spinner
            from kivy.uix.textinput import TextInput
            from kivy.uix.checkbox import CheckBox
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style

            def style(css):
                return resolve_style(
                    parse_stylesheet("button {" + css + "}"),
                    StyleTarget("button"),
                )
            bottom = style(
                "border-bottom-width:2px; border-bottom-color:#123456;"
                "border-radius:8px;"
            )
            rounded = style(
                "border-bottom-width:2px; border-bottom-color:#123456;"
                "border-radius:12px;"
            )
            top = style(
                "border-top-width:3px; border-top-color:#aabbcc;"
                "border-radius:0px;"
            )
            empty = style("")
            renderer = KivyRenderer()
            for name, widget in (
                ("Button", Button()), ("Input", TextInput(multiline=False)),
                ("TextArea", TextInput(multiline=True)),
                ("Select", Spinner()), ("Link", Button()),
                ("Checkbox", CheckBox()),
            ):
                widget.size_hint = (None, None)
                widget.size = (180, 45)
                handle = KivyHandle(name, widget, {})
                renderer.apply_css(handle, bottom)
                group, redraw, sides, lines = widget._psx_css_control_side_strokes
                assert len(sides) == len(lines) == 1, (name, sides)
                assert sides[0][0] == "bottom", (name, sides)
                assert abs(lines[0][2].width - 2) < 0.01
                old_points = tuple(lines[0][2].points)
                widget.pos = (4, 7)
                assert tuple(lines[0][2].points) != old_points
                renderer.apply_css(handle, rounded)
                assert widget._psx_css_control_side_strokes[0] is group
                assert widget._psx_css_control_side_radius == 12
                renderer.apply_css(handle, top)
                assert widget._psx_css_control_side_strokes[0] is not group
                assert widget._psx_css_control_side_strokes[2][0][0] == "top"
                renderer.apply_css(handle, empty)
                assert not hasattr(widget, "_psx_css_control_side_strokes")
                assert group not in tuple(widget.canvas.after.children)
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_control_text_align_respects_padding_and_resize_then_resets(self):
        """Native Label.halign needs an authored content-width text_size."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.button import Button
            from kivy.uix.spinner import Spinner
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style

            def style(decls):
                return resolve_style(parse_stylesheet(
                    "button {" + decls + "}"
                ), StyleTarget("button"))
            renderer = KivyRenderer()
            aligned = style("text-align:right; padding:0px 10px")
            empty = style("")
            for kind, widget in (
                ("Button", Button(text="Save")),
                ("Select", Spinner(text="One")),
                ("Link", Button(text="Go")),
            ):
                widget.size_hint = (None, None)
                widget.size = (160, 40)
                original = tuple(widget.text_size)
                handle = KivyHandle(kind, widget, {})
                renderer.apply_css(handle, aligned)
                assert widget.halign == "right", (kind, widget.halign)
                # Qt currently certifies CSS internal padding only for
                # Button; Select and Link preserve their native padding.
                inset = 20 if kind == "Button" else 0
                assert abs(widget.text_size[0] - (160 - inset)) < 1, (
                    kind, widget.text_size, widget.padding
                )
                widget.width = 200
                assert abs(widget.text_size[0] - (200 - inset)) < 1, (
                    kind, widget.text_size, widget.padding
                )
                renderer.apply_css(handle, empty)
                assert tuple(widget.text_size) == original, (
                    kind, widget.text_size, original
                )
                assert not hasattr(widget, "_psx_css_text_align_resize")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_authored_css_foreground_survives_disabled_control_states(self):
        """CSS color remains authored while disabled, and resets both paints."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.uix.button import Button
            from kivy.uix.spinner import Spinner
            from kivy.uix.textinput import TextInput
            from kivy.uix.label import Label
            from psx.renderers.kivy.kivy import KivyRenderer, KivyHandle
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style

            def style(value):
                return resolve_style(
                    parse_stylesheet("button {" + value + "}"),
                    StyleTarget("button"),
                )
            authored = style("color:#a1b2c3")
            empty = style("")
            renderer = KivyRenderer()
            for name, widget, normal, disabled in (
                ("Button", Button(), "color", "disabled_color"),
                ("Select", Spinner(), "color", "disabled_color"),
                ("Input", TextInput(), "foreground_color", "disabled_foreground_color"),
                ("TextArea", TextInput(multiline=True), "foreground_color", "disabled_foreground_color"),
            ):
                if not hasattr(widget, disabled):
                    continue
                before = (tuple(getattr(widget, normal)), tuple(getattr(widget, disabled)))
                widget.disabled = True
                handle = KivyHandle(name, widget, {})
                renderer.apply_css(handle, authored)
                rgb = (161 / 255, 178 / 255, 195 / 255)
                for attr in (normal, disabled):
                    actual = getattr(widget, attr)
                    assert all(abs(a-b)<1e-5 for a, b in zip(actual[:3], rgb)), (
                        name, attr, actual
                    )
                renderer.apply_css(handle, empty)
                assert (tuple(getattr(widget, normal)),
                        tuple(getattr(widget, disabled))) == before, name
                assert widget.disabled
            label = Label()
            handle = KivyHandle("Text", label, {"value":"Save"})
            renderer.apply_css(handle, authored)
            assert tuple(label.disabled_color[:3]) == tuple(label.color[:3])
            renderer.apply_css(handle, empty)
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_badge_font_uses_current_drawable_scale_not_fixed_double_size(self):
        """Badge presentation follows the live screen scale without remount."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from psx import Badge
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer

            renderer = KivyRenderer()
            tree = Reconciler(renderer)
            mounted = tree.render(Badge(label="READY"))
            handle = mounted.handle
            widget = handle.widget
            base = widget.font_size
            logical_scale = widget._psx_badge_pixel_scale
            assert logical_scale == renderer._psx_css_pixel_scale
            # Shared Badge font is point-sized in Qt; Kivy converts it
            # at CSS 96/72 DPI, not an unconditional 2x multiplier.
            assert abs(base - 12 * (96 / 72) * logical_scale) < 0.02
            renderer._psx_css_pixel_scale = logical_scale * 2
            renderer._scale_component_font(handle)
            assert widget.font_size == base * 2
            assert mounted.handle.widget is widget
            renderer._psx_css_pixel_scale = logical_scale
            renderer._scale_component_font(handle)
            assert abs(widget.font_size - base) < 0.02
            tree.unmount()
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_css_button_background_overrides_kivy_theme(self) -> None:
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1"})
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent("""
            from psx import Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style
            renderer = KivyRenderer()
            reconciler = Reconciler(renderer)
            instance = reconciler.render(Button("Resumen"))
            widget = instance.handle.widget
            original = (widget.background_normal, widget.background_down)
            first = resolve_style(
                parse_stylesheet("button {background: #3b6ef5; padding: 0px 10px}"), StyleTarget("button"))
            renderer.apply_css(instance.handle, first)
            assert hasattr(widget, "_psx_css_button_background")
            assert list(widget.padding) == [10, 0, 10, 0]
            assert widget.background_normal == "" and widget.background_down == ""
            assert tuple(round(x, 4) for x in widget._psx_css_button_background[2].rgba) == (
                round(59/255, 4), round(110/255, 4), round(245/255, 4), 1)
            renderer.apply_css(instance.handle, resolve_style(
                parse_stylesheet("button {color: #ffffff}"), StyleTarget("button")))
            assert not hasattr(widget, "_psx_css_button_background")
            assert (widget.background_normal, widget.background_down) == original
            reconciler.unmount()
        """)
        result = subprocess.run([sys.executable, "-c", script],
                                env=environment, capture_output=True, text=True)
        if "Unable to get a Window" in result.stderr or "Unable to get a Window" in result.stdout:
            self.skipTest("No usable Kivy window provider.")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_css_button_font_reset_respects_updated_component_prop(self) -> None:
        """A keyed Button update must not restore its first-mount font size."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from psx import Button
            from psx.core.reconcile import Reconciler
            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.css.parser import parse_stylesheet
            from psx.css.cascade import StyleTarget, resolve_style

            renderer = KivyRenderer()
            reconciler = Reconciler(renderer)
            instance = reconciler.render(Button("Save", font_size=14))
            handle = instance.handle
            widget = handle.widget
            styled = resolve_style(parse_stylesheet(
                "button { font-size: 16px; }"
            ), StyleTarget("button"))
            unstyled = resolve_style(parse_stylesheet(""), StyleTarget("button"))
            renderer.apply_css(handle, styled)
            assert widget.font_size == 16
            renderer.update(handle, {"font_size": 22}, frozenset())
            renderer.apply_css(handle, styled)
            assert widget.font_size == 16
            renderer.apply_css(handle, unstyled)
            assert widget.font_size == 22
            assert handle.widget is widget
            reconciler.unmount()
        """)
        result = subprocess.run(
            [sys.executable, "-c", script], env=environment,
            capture_output=True, text=True, timeout=90,
        )
        if "Unable to get a Window" in result.stderr:
            self.skipTest("No usable Kivy window provider.")
        self.assertEqual(result.returncode, 0, result.stdout + "\\n" + result.stderr)

    def test_counter_preserves_button_identity_and_uses_clock_scheduler(self) -> None:
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1"})
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent(
            """
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.clock import Clock
            from psx import App, Button, Checkbox, Flex, Text, component, use_state

            @component
            def Counter():
                value, set_value = use_state(0)
                return Flex(Text(str(value), key="text"), Button("+", key="button", on_click=lambda: set_value(value + 1)), direction="column")

            from psx.renderers.kivy.kivy import KivyRenderer
            from psx.sfle.engine import PythonLayoutEngine
            from psx.sfle.model import AvailableSize, LayoutConstraints
            renderer = KivyRenderer(
                sfle_constraints=LayoutConstraints(
                    AvailableSize(400, True), AvailableSize(320, True)),
                engine=PythonLayoutEngine(),
            )
            app = App(Counter(), renderer=renderer)
            app.mount()
            column = app.reconciler.root.children[0].handle
            label, button = column.children
            native_button = button.widget
            native_button.dispatch("on_release")
            Clock.tick()
            assert label.widget.text == "1"
            assert button.widget is native_button
            app.unmount()
            from kivy.uix.label import Label
            from psx.core.reconcile import Reconciler
            r = Reconciler(app.renderer)
            root = r.render(Flex(Text("old", font_size=24, bold=True, italic=True,
                                        color="#336699", align="right", enabled=False)))
            label = root.children[0].handle.widget
            assert isinstance(label, Label) and label.text == "old"
            assert label.font_size == 24 and label.bold and label.italic and label.disabled
            assert label.halign == "right"
            assert list(label.color) == [0.2, 0.4, 0.6, 1]
            r.render(Flex(Text("new", font_size=12, color="#112233", align="center")))
            assert r.root.children[0].handle.widget is label and label.text == "new"
            assert label.font_size == 12 and not label.bold and not label.italic and not label.disabled
            assert label.halign == "center"
            assert list(label.color) == [17/255, 34/255, 51/255, 1]
            r.render(Flex(Text("theme")))
            assert list(label.color) == list(label.property("color").defaultvalue)
            assert list(label.disabled_color) == list(label.property("disabled_color").defaultvalue)
            label.size = (300, 60)
            assert tuple(label.text_size) == (300, 60)
            r.render(Flex())
            assert label.parent is None and r.root.handle.children == []
            label.size = (400, 80)
            assert tuple(label.text_size) == (300, 60)  # size subscription cleaned up
            r.unmount()
            changes = []
            leaf_renderer = KivyRenderer()
            r = Reconciler(leaf_renderer)
            check = r.render(Checkbox(on_change=changes.append)).handle.widget
            check.active = True
            assert changes == [True]
            r.render(Checkbox(checked=True, on_change=changes.append))
            assert r.root.handle.widget is check and check.active
            r.unmount()
            """
        )
        result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True, text=True)
        if "Unable to get a Window" in result.stderr or "Unable to get a Window" in result.stdout:
            self.skipTest("Kivy is installed but this test host has no usable native window provider.")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_flex_has_explicit_flex_route_without_boxlayout_fallback(self) -> None:
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1"})
        environment["PYTHONPATH"] = "src" + os.pathsep + environment.get("PYTHONPATH", "")
        script = textwrap.dedent("""
            from psx import Flex, Text
            from psx.core.errors import RendererCapabilityError
            from psx.renderers.kivy.kivy import KivyRenderer

            renderer = KivyRenderer()
            assert renderer.adapters.get("Flex") is not None
            try:
                renderer.create(Flex(Text("A")), None)
            except RendererCapabilityError as exc:
                assert "Native SFLE SFLE geometry" in str(exc)
            else:
                raise AssertionError("Flex silently delegated geometry to native Kivy")
        """)
        result = subprocess.run([sys.executable, "-c", script], env=environment,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
