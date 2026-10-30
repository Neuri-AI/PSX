from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class KivyRendererSubprocessTests(unittest.TestCase):

    def test_retina_text_font_uses_kivy_scaled_sp(self) -> None:
        """Authored CSS px fonts must not shrink to half-size on Retina."""
        environment = dict(os.environ)
        environment.update({"KIVY_NO_FILELOG": "1", "KIVY_NO_ARGS": "1"})
        script = textwrap.dedent("""
            from kivy.config import Config
            Config.set("graphics", "window_state", "hidden")
            from kivy.metrics import Metrics, sp
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
                    assert abs(widget.font_size - sp(14)) < 0.01
                    # Authored CSS font-size / line-height are both scaled;
                    # the dimensionless line_height remains stable.
                    handle = KivyHandle("Text", widget, {"value": "Hello"})
                    style = resolve_style(
                        parse_stylesheet("p {font-size: 16px; line-height: 24px}"),
                        StyleTarget("p"),
                    )
                    renderer.apply_css(handle, style)
                    assert abs(widget.font_size - sp(16)) < 0.01
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
