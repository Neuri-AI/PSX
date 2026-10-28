from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import Button, Checkbox, Flex, Text, component, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter import TkinterRenderer
from tests.certification.tk_public_driver import configured_font_size


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



    def test_button_css_background_without_typography(self):
        from tkinter import ttk
        from psx.css.parser import parse_stylesheet
        from psx.css.cascade import StyleTarget, resolve_style
        self._enable_native_sfle()
        instance = self.reconciler.render(Flex(Button("Resumen"), direction="row")).children[0]
        widget = instance.handle.widget
        rule = resolve_style(
            parse_stylesheet("button { background: #3b6ef5; cursor: pointer; padding: 0px 10px; }"),
            StyleTarget("button"),
        )
        self.renderer.apply_css(instance.handle, rule)
        name = str(widget.cget("style"))
        self.assertEqual(ttk.Style(widget).lookup(name, "background"), "#3b6ef5")
        self.assertEqual(str(widget.cget("cursor")), "hand2")
        padding = ttk.Style(widget).lookup(name, "padding")
        self.assertEqual(tuple(int(x) for x in padding), (10, 0, 10, 0))



    def test_button_padding_and_active_colors_without_font_declarations(self):
        from tkinter import ttk
        from psx.css.parser import parse_stylesheet
        from psx.css.cascade import StyleTarget, resolve_style
        self._enable_native_sfle()
        instance = self.reconciler.render(Flex(Button("Usuarios"), direction="row")).children[0]
        widget = instance.handle.widget
        computed = resolve_style(parse_stylesheet(
            "button {padding: 0px 10px; text-align: left; "
            "cursor: pointer; color: #6b7385;}"
        ), StyleTarget("button"))
        self.renderer.apply_css(instance.handle, computed)
        theme = ttk.Style(widget)
        name = str(widget.cget("style"))
        self.assertEqual(tuple(int(v) for v in theme.lookup(name, "padding")), (10, 0, 10, 0))
        self.assertEqual(theme.lookup(name, "anchor"), "w")
        self.assertEqual(theme.lookup(name, "foreground"), "#6b7385")
        self.assertEqual(str(widget.cget("cursor")), "hand2")
        selected = resolve_style(parse_stylesheet(
            "button {padding: 0px 10px; background: #3b6ef5; color: #fff;}"
        ), StyleTarget("button"))
        self.renderer.apply_css(instance.handle, selected)
        self.assertEqual(theme.lookup(name, "background"), "#3b6ef5")
        self.assertEqual(theme.lookup(name, "foreground"), "#ffffff")

    @unittest.skipIf(sys.platform == "darwin", "Aqua buttons use the classic Tk paint bridge.")
    def test_styled_ttk_button_uses_authored_canvas_paint_and_resets(self):
        from psx import psx

        self._enable_native_sfle()
        self.renderer.root.deiconify()
        self.addCleanup(self.renderer.root.withdraw)
        markup = lambda bg, radius: psx(
            '<div style="background: #1f2430">'
            '<button key="action" style="width: 180px; height: 38px;'
            'border: none; border-radius: ' + str(radius) + 'px;'
            'background: ' + bg + '; color: #ffffff">'
            'Reportes</button></div>'
        )
        first = self.reconciler.render(markup("#3b6ef5", 8))
        button = first.children[0].handle.widget
        surface = button._psx_css_button_surface
        self.renderer.root.update()
        self.assertTrue(surface.winfo_exists())
        self.assertEqual(str(surface.cget("background")), "#1f2430")
        painted = surface.find_withtag("psx-css-button-fill")
        self.assertTrue(painted)
        self.assertTrue(all(
            surface.itemcget(item, "fill") == "#3b6ef5" for item in painted
        ))
        self.assertEqual(
            surface.itemcget(surface.find_withtag("psx-css-button-text")[0], "fill"),
            "#ffffff",
        )

        updated = self.reconciler.render(markup("#26ad83", 12))
        self.assertIs(updated.children[0].handle.widget, button)
        self.assertIs(button._psx_css_button_surface, surface)
        painted = surface.find_withtag("psx-css-button-fill")
        self.assertTrue(painted)
        self.assertTrue(all(
            surface.itemcget(item, "fill") == "#26ad83" for item in painted
        ))

        reset = self.reconciler.render(
            psx('<div style="background: #1f2430"><button key="action">Reportes</button></div>')
        )
        self.assertIs(reset.children[0].handle.widget, button)
        self.assertFalse(hasattr(button, "_psx_css_button_surface"))
        self.assertFalse(surface.winfo_exists())

    @unittest.skipIf(sys.platform == "darwin", "Aqua buttons use the classic Tk paint bridge.")
    def test_transparent_styled_ttk_button_tracks_parent_and_dispatches_once(self):
        from psx import psx

        self._enable_native_sfle()
        self.renderer.root.deiconify()
        self.addCleanup(self.renderer.root.withdraw)
        clicked = []

        def view(parent_color, disabled):
            return psx(
                '<div style="background: ' + parent_color + '">'
                '<button key="action" enabled={allowed}'
                ' style="width: 180px; height: 38px; border: none;'
                'border-radius: 8px; padding: 0px 10px; color: #6b7385">'
                'Usuarios</button></div>',
                scope={"allowed": not disabled},
            )

        # Use the native Button event slot; Canvas must never bypass it.
        initial = self.reconciler.render(view("#1f2430", False))
        button_instance = initial.children[0]
        button = button_instance.handle.widget
        surface = button._psx_css_button_surface
        self.renderer.root.update()
        self.assertTrue(all(
            surface.itemcget(i, "fill") == "#1f2430"
            for i in surface.find_withtag("psx-css-button-fill")
        ))
        self.assertEqual(surface.cget("background"), "#1f2430")

        changed = self.reconciler.render(view("#273448", False))
        self.assertIs(changed.children[0].handle.widget, button)
        self.assertIs(button._psx_css_button_surface, surface)
        self.assertTrue(all(
            surface.itemcget(i, "fill") == "#273448"
            for i in surface.find_withtag("psx-css-button-fill")
        ))

        # After a native callback is bound, the owned surface activates the
        # current callback exactly once; disabling the control prevents it.
        from psx.core.events import EventSlot
        slot = EventSlot(lambda: clicked.append("clicked"))
        subscription = self.renderer.bind_event(button_instance.handle, "on_click", slot)
        self.addCleanup(lambda: self.renderer.unbind_event(subscription))
        self.renderer.root.update()
        surface.event_generate("<ButtonPress-1>", x=10, y=10)
        surface.event_generate("<ButtonRelease-1>", x=10, y=10)
        self.assertEqual(clicked, ["clicked"])
        self.reconciler.render(view("#273448", True))
        self.renderer.root.update()
        surface.event_generate("<ButtonPress-1>", x=10, y=10)
        surface.event_generate("<ButtonRelease-1>", x=10, y=10)
        self.assertEqual(clicked, ["clicked"])

    def test_css_button_paint_preserves_component_pixel_font_size(self):
        from tkinter import ttk
        from psx.css.cascade import StyleTarget, resolve_style
        from psx.css.parser import parse_stylesheet

        self._enable_native_sfle()
        instance = self.reconciler.render(
            Flex(Button("Reportes", font_size=23), direction="row")
        ).children[0]
        widget = instance.handle.widget
        native_style = str(widget.cget("style"))
        self.assertTrue(ttk.Style(widget).lookup(native_style, "font"))

        def style(css):
            return resolve_style(parse_stylesheet("button {" + css + "}"),
                                 StyleTarget("button"))

        self.renderer.apply_css(instance.handle, style(
            "background: #3b6ef5; color: #ffffff; padding: 0px 10px;"
        ))
        font = widget._psx_css_native_font
        self.assertEqual(font.cget("size"), -23)
        self.assertEqual(
            widget._psx_css_button_surface.itemcget(
                widget._psx_css_button_surface.find_withtag(
                    "psx-css-button-text"
                )[0], "font",
            ), str(font),
        )

        self.renderer.apply_css(instance.handle, style(
            "background: #26ad83; color: #ffffff; font-size: 19px;"
        ))
        self.assertEqual(font.cget("size"), -19)
        self.renderer.apply_css(instance.handle, style(
            "background: #26ad83; color: #ffffff;"
        ))
        self.assertEqual(font.cget("size"), -23)

        self.renderer.apply_css(instance.handle, None)
        self.assertEqual(str(widget.cget("style")), native_style)
        self.assertFalse(hasattr(widget, "_psx_css_button_surface"))

    def test_css_input_color_preserves_component_pixel_font_size(self):
        from psx import Input
        from psx.css.cascade import StyleTarget, resolve_style
        from psx.css.parser import parse_stylesheet

        self._enable_native_sfle()
        instance = self.reconciler.render(
            Flex(Input(value="Sample", font_size=22), direction="row")
        ).children[0]
        widget = instance.handle.widget
        native_font = str(widget.cget("font"))
        color_only = resolve_style(
            parse_stylesheet("input {color: #112233;}"),
            StyleTarget("input"),
        )
        self.renderer.apply_css(instance.handle, color_only)
        self.assertEqual(widget._psx_css_native_font.cget("size"), -22)
        self.assertEqual(str(widget.cget("font")), str(widget._psx_css_native_font))

        self.renderer.apply_css(instance.handle, None)
        self.assertEqual(str(widget.cget("font")), native_font)

    def test_css_text_font_stack_renders_with_installed_fallback(self):
        """X11 must select the next installed face, not a missing first name."""
        import re
        from tkinter import font as tkfont
        from psx import psx

        self._enable_native_sfle()
        available = next(
            name for name in tkfont.families(root=self.root)
            if re.fullmatch(r"[a-zA-Z0-9 _.-]+", name)
        )
        missing = "PSXFontThatDoesNotExistInTheSystem"
        view = lambda size, stack: psx(
            '<div><span key="label" style="font-family: ' + stack
            + '; font-size: ' + str(size)
            + 'px; color: #112233">Typography</span></div>'
        )
        first = self.reconciler.render(
            view(18, "'" + missing + "', '" + available + "', sans-serif")
        )
        label = first.children[0].children[0].handle.widget
        native_font = label._psx_text_font
        self.assertEqual(native_font.cget("family").casefold(),
                         available.casefold())
        self.assertEqual(native_font.cget("size"), -18)
        self.assertEqual(str(label.cget("font")), str(native_font))
        baseline = native_font.measure("Typography")

        next_render = self.reconciler.render(
            view(24, "'" + missing + "', '" + available + "', sans-serif")
        )
        self.assertIs(next_render.children[0].children[0].handle.widget, label)
        self.assertEqual(native_font.cget("size"), -24)
        self.assertGreater(native_font.measure("Typography"), baseline)

        self.reconciler.render(psx(
            '<div><span key="label">Typography</span></div>'
        ))
        self.assertEqual(native_font.cget("size"), -16)
        self.assertFalse(native_font.cget("family") == missing)

    def test_css_tk_button_paint_uses_the_fallback_font(self):
        import re
        from tkinter import font as tkfont
        from psx import psx

        self._enable_native_sfle()
        available = next(
            name for name in tkfont.families(root=self.root)
            if re.fullmatch(r"[a-zA-Z0-9 _.-]+", name)
        )
        view = psx(
            '<div><button key="action" style="width: 190px; height: 42px;'
            'background: #3b6ef5; color: #ffffff; font-size: 21px;'
            'font-family: PSXMissingFace, \''
            + available + "\'; border-radius: 8px"
            '">Reportes</button></div>'
        )
        mounted = self.reconciler.render(view)
        button = mounted.children[0].handle.widget
        font = button._psx_css_native_font
        self.assertEqual(font.cget("family").casefold(), available.casefold())
        self.assertEqual(font.cget("size"), -21)
        if sys.platform != "darwin":
            canvas = button._psx_css_button_surface
            text_id = canvas.find_withtag("psx-css-button-text")[0]
            self.assertEqual(canvas.itemcget(text_id, "font"), str(font))

    def test_heading_class_css_controls_actual_tk_text_font(self):
        """A class on h5 must reach the native Text child, not only its box."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tkinter import font as tkfont
        from psx import psx
        from psx.css.context import css_context

        self._enable_native_sfle()
        installed = tkfont.families(root=self.root)
        selected = next(name for name in installed
                        if "cantarell" in name.casefold()) if any(
                            "cantarell" in name.casefold() for name in installed
                        ) else tkfont.nametofont(
                            "TkDefaultFont", root=self.root).actual("family")
        with TemporaryDirectory() as directory:
            Path(directory, "styles.css").write_text(
                ".prueba {font-family: '" + selected +
                "', sans-serif; font-size: 29px; font-weight: 700;}"
            )
            with css_context(stylesheets=("styles.css",), root=directory):
                view = psx(
                    '<div class="container"><div class="activity-card">'
                    '<h5 class="prueba">Actividad Reciente</h5>'
                    '</div></div>'
                )
            # Confirm the style was computed on both formatting host and
            # the real Text node before testing toolkit projection.
            heading = view.children[0].children[0]
            text = heading.children[0]
            self.assertIn("font-size", heading.css_computed.specified)
            self.assertIn("font-size", text.css_computed.specified)
            mounted = self.reconciler.render(view)
            label = mounted.children[0].children[0].handle.widget
            native_font = label._psx_text_font
            self.assertEqual(native_font.cget("size"), -29)
            self.assertEqual(native_font.actual("weight"), "bold")
            self.assertEqual(native_font.actual("family").casefold(),
                             selected.casefold())
            self.assertEqual(str(label.cget("font")), str(native_font))

    def test_html_box_background_uses_native_theme_independent_fill(self):
        from psx.markup.compile import psx
        self._enable_native_sfle()
        instance = self.reconciler.render(
            psx('<div style="background-color: #f5f6f8;">Card</div>')
        )
        widget = instance.handle.widget
        self.assertTrue(hasattr(widget, "_psx_css_fill_canvas"))
        self.assertEqual(str(widget._psx_css_fill_canvas.cget("background")), "#f5f6f8")

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
                direction="column", width=f"{640 - 2 * padding}px",
                height=f"{480 - 2 * padding}px", padding=padding, gap=gap,
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

    def test_text_portable_update_and_clean_destruction(self) -> None:
        from tkinter import ttk
        from tkinter.font import Font
        label = self.reconciler.render(Text("old", font_size=24, bold=True, italic=True,
                                             color="#336699", align="right", enabled=False)).handle.widget
        self.assertIsInstance(label, tk.Label if sys.platform == 'darwin' else ttk.Label)
        font = Font(root=label, font=label.cget("font"))
        self.assertEqual(configured_font_size(label), 24)
        self.assertEqual(font.actual("weight"), "bold")
        self.assertEqual(font.actual("slant"), "italic")
        self.assertEqual(str(label.cget("foreground")), "#336699")
        self.assertEqual(str(label.cget("anchor")), "e")
        self.assertEqual(label.cget("state"), "disabled") if sys.platform == "darwin" else self.assertTrue(label.instate(("disabled",)))
        self.reconciler.render(Text("new", font_size=12, color="#112233", align="center"))
        self.assertIs(self.reconciler.root.handle.widget, label)
        self.assertEqual(label.cget("text"), "new")
        font = Font(root=label, font=label.cget("font"))
        self.assertEqual(configured_font_size(label), 12)
        self.assertEqual(font.actual("weight"), "normal")
        self.assertEqual(font.actual("slant"), "roman")
        self.assertEqual(str(label.cget("foreground")), "#112233")
        self.assertEqual(str(label.cget("anchor")), "center")
        self.assertEqual(label.cget("state"), "normal") if sys.platform == "darwin" else self.assertTrue(label.instate(("!disabled",)))
        self.reconciler.render(Text("theme"))
        self.assertEqual(str(label.cget("foreground")), str(label._psx_text_original_foreground) if sys.platform == "darwin" else "")
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
