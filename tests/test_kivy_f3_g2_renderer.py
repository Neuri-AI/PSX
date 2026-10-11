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

            from psx import Flex, Text, Button, Checkbox, component, use_state, psx
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

            # Unported component: no fallback to Kivy BoxLayout.
            backend, tree = create()
            try:
                tree.render(Flex(Checkbox(), width=160, height=80))
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
