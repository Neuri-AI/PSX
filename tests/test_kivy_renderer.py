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
