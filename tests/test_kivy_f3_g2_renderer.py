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

            from psx import Flex, Text, Button, Checkbox, Slider, Spacer, Image, component, use_state, psx
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
                tree.render(Flex(Checkbox(), width=160, height=80))
            except RendererCapabilityError as error:
                assert "explicit pixel layout_width" in str(error)
            else:
                raise AssertionError("Kivy Checkbox with auto size bypassed capability gate")
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
                tree.render(Flex(Image("unported.png"), width=160, height=80))
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
