"""F3-G2 Qt-family parity against real widgets, isolated by binding in CI.

Run this module once per process with PSX_QT_BINDING=pyside6|pyqt6|pyqt5|pyside2.
No binding is silently skipped; install failures are CI failures. Exact SFLE
coordinates are identical across bindings; font painting is toolkit-dependent.
"""
from __future__ import annotations

import importlib
import os
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psx import Button, Checkbox, Flex, Input, Native, ProgressBar, Text, component, psx, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.f3_external import SFLEExternalPort
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, Rect, LayoutResult

BINDING = os.environ.get("PSX_QT_BINDING")
VALID = {"pyside6", "pyqt6", "pyqt5", "pyside2"}
if BINDING not in VALID:
    raise RuntimeError("PSX_QT_BINDING must select exactly one Qt binding.")

PACKAGE = {
    "pyside6": "PySide6", "pyqt6": "PyQt6",
    "pyqt5": "PyQt5", "pyside2": "PySide2",
}[BINDING]
qtwidgets = importlib.import_module(f"{PACKAGE}.QtWidgets")
if BINDING.startswith("pyside"):
    facades = importlib.import_module("psx.renderers.qt.pyside")
else:
    facades = importlib.import_module("psx.renderers.qt.pyqt")
RENDERER_CLASS = getattr(facades, f"{PACKAGE}Renderer")


def viewport(w=160, h=80):
    return LayoutConstraints(AvailableSize(w, True), AvailableSize(h, True))


def button(label, key, width, *, on_click=None):
    props = {
        "key": key,
        "layout_width": f"{width}px", "layout_height": "20px",
        "flex_basis": f"{width}px", "flex_shrink": 0,
    }
    if on_click is not None:
        props["on_click"] = on_click
    return Button(label, **props)


def geometry(widget):
    rect = widget.geometry()
    return (rect.x(), rect.y(), rect.width(), rect.height())


class QtFamilySFLEParityTests(unittest.TestCase):
    def setUp(self):
        self.renderer = RENDERER_CLASS(
            argv=["psx-qt-family", BINDING],
            sfle_constraints=viewport(), engine=PythonLayoutEngine(),
        )
        self.reconciler = Reconciler(self.renderer)

    def tearDown(self):
        self.reconciler.unmount()
        self.renderer.application.processEvents()

    def test_binding_and_native_geometry_owner(self):
        self.assertEqual(self.renderer._binding, BINDING)
        self.assertIs(self.renderer._widgets, qtwidgets)
        root = self.reconciler.render(Flex(
            Text("A", key="a", layout_width="40px", layout_height="20px",
                 flex_basis="40px", flex_shrink=0),
            button("B", "b", 30), direction="row", gap=8,
            width="160px", height="80px", align_items="flex-start",
        ))
        self.assertIsNone(root.handle.widget.layout())
        left, right = (node.handle.widget for node in root.children)
        self.assertIsInstance(left, qtwidgets.QLabel)
        self.assertIsInstance(right, qtwidgets.QPushButton)
        self.assertIs(left.parentWidget(), root.handle.widget)
        self.assertIs(right.parentWidget(), root.handle.widget)
        self.assertEqual(geometry(left), (0, 0, 40, 20))
        self.assertEqual(geometry(right), (48, 0, 30, 20))
        self.assertEqual(self.renderer.sfle_result.geometry_commit_error, 0.0)

    def test_markup_nested_padding_and_local_coordinates(self):
        root = self.reconciler.render(psx("""
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
        """))
        outer, inner = root.handle.widget, root.children[0].handle.widget
        a, b = (child.handle.widget for child in root.children[0].children)
        self.assertIsNone(inner.layout())
        self.assertIs(inner.parentWidget(), outer)
        self.assertEqual(geometry(inner), (10, 10, 120, 40))
        self.assertEqual(geometry(a), (0, 0, 30, 15))
        self.assertEqual(geometry(b), (36, 0, 20, 15))

    def test_native_controls_have_identical_sfle_rectangles(self):
        from psx import Slider, Select
        root = self.reconciler.render(Flex(
            Checkbox(checked=True, key="cb", layout_width="25px",
                     layout_height="24px", flex_basis="25px", flex_shrink=0),
            Input(value="hello", key="entry", layout_width="60px",
                  layout_height="24px", flex_basis="60px", flex_shrink=0),
            Slider(value=50, key="slider", layout_width="35px",
                   layout_height="24px", flex_basis="35px", flex_shrink=0),
            width=160, height=80, gap=5, align_items="flex-start",
        ))
        w = [node.handle.widget for node in root.children]
        self.assertIsInstance(w[0], qtwidgets.QCheckBox)
        self.assertIsInstance(w[1], qtwidgets.QLineEdit)
        self.assertIsInstance(w[2], qtwidgets.QSlider)
        self.assertEqual([geometry(v) for v in w],
                         [(0, 0, 25, 24), (30, 0, 60, 24), (95, 0, 35, 24)])
        self.assertTrue(w[0].isChecked())
        self.assertEqual(w[1].text(), "hello")
        self.assertEqual(self.renderer.sfle_result.geometry_commit_error, 0.0)

    def test_keyed_reconciliation_and_button_event_rebind(self):
        events = []
        first = self.reconciler.render(Flex(
            button("A", "a", 30, on_click=lambda: events.append("old")),
            button("B", "b", 20),
            width=160, height=80, gap=4, align_items="flex-start",
        ))
        a, b = (child.handle.widget for child in first.children)
        a.click()
        after = self.reconciler.render(Flex(
            button("B", "b", 20),
            button("A", "a", 30, on_click=lambda: events.append("new")),
            width=160, height=80, gap=9, align_items="flex-start",
        ))
        self.assertIs(after.children[0].handle.widget, b)
        self.assertIs(after.children[1].handle.widget, a)
        self.assertEqual((b.x(), a.x()), (0, 29))
        a.click()
        self.assertEqual(events, ["old", "new"])

    def test_state_update_recommits_without_widget_remount(self):
        setters = []

        @component
        def Counter():
            n, set_n = use_state(0)
            setters.append(set_n)
            return Flex(
                button("Count", "btn", 20 + 10 * n),
                width=160, height=80,
            )

        root = self.reconciler.render(Counter())
        native = root.children[0].children[0].handle.widget
        self.assertEqual(native.width(), 20)
        setters[-1](2)
        self.renderer.application.processEvents()
        self.assertIs(root.children[0].children[0].handle.widget, native)
        self.assertEqual(native.width(), 40)

    def test_viewport_recompute_without_native_remount(self):
        root = self.reconciler.render(Flex(
            button("B", "b", 40), width="100%", height="100%",
        ))
        before = root.children[0].handle.widget
        previous = self.renderer.sfle_result.generation
        self.renderer.set_sfle_constraints(viewport(220, 120))
        self.renderer.commit_layout(root)
        self.assertIs(root.children[0].handle.widget, before)
        self.assertGreater(self.renderer.sfle_result.generation, previous)
        self.assertIsNone(root.handle.widget.layout())

    def test_native_owned_geometry_port_and_readback(self):
        calls = []
        def measure(widget, c):
            calls.append("measure")
            return IntrinsicSizes(10, 30, 8, 20, 30, 20)
        def apply(widget, rect):
            calls.append(("apply", rect))
            widget.setGeometry(round(rect.x), round(rect.y),
                               round(rect.width), round(rect.height))
        def read(widget):
            calls.append("read")
            g = widget.geometry()
            return Rect(g.x(), g.y(), g.width(), g.height())

        root = self.reconciler.render(Flex(
            Native(qtwidgets.QLabel, renderer=BINDING,
                   sfle_port=SFLEExternalPort(measure, apply, read),
                   layout_width="30px", layout_height="18px",
                   flex_basis="30px", flex_shrink=0),
            width=160, height=80,
        ))
        w = root.children[0].handle.widget
        self.assertIsInstance(w, qtwidgets.QLabel)
        self.assertIs(w.parentWidget(), root.handle.widget)
        self.assertEqual(geometry(w), (0, 0, 30, 18))
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(0, 0, 30, 18)), calls)
        self.assertIn("read", calls)

    def test_native_binding_is_inferred_for_selected_toolkit(self):
        inferred = Native(
            qtwidgets.QLabel,
            sfle_port=SFLEExternalPort(
                measure=lambda w, c: IntrinsicSizes(4, 12, 4, 14, 12, 14),
                apply=lambda w, r: w.setGeometry(
                    round(r.x), round(r.y), round(r.width), round(r.height),
                ),
                read=lambda w: Rect(w.x(), w.y(), w.width(), w.height()),
            ),
            layout_width="12px", layout_height="14px",
            flex_basis="12px", flex_shrink=0,
        )
        self.assertEqual(inferred.type.renderer, BINDING)
        root = self.reconciler.render(Flex(inferred, width=160, height=80))
        self.assertEqual(geometry(root.children[0].handle.widget), (0, 0, 12, 14))

    def test_additional_certified_controls_preserve_native_types_and_geometry(self):
        from psx import Radio, Select
        specs = [
            (Radio("r", label="Pick", key="radio",
                   layout_width="70px", layout_height="24px",
                   flex_basis="70px", flex_shrink=0), qtwidgets.QRadioButton, 70),
            (ProgressBar(value=40, key="progress",
                         layout_width="110px", layout_height="24px",
                         flex_basis="110px", flex_shrink=0), qtwidgets.QProgressBar, 110),
            (Select(options=["Alpha", "Beta"], value="Beta", key="select",
                    layout_width="100px", layout_height="24px",
                    flex_basis="100px", flex_shrink=0), qtwidgets.QComboBox, 100),
        ]
        root = self.reconciler.render(Flex(
            *(node for node, _, _ in specs),
            width="300px", height="80px", gap=5, align_items="flex-start",
        ))
        x = 0
        for (vnode, expected_class, width), instance in zip(specs, root.children):
            widget = instance.handle.widget
            self.assertIsInstance(widget, expected_class, vnode.type)
            self.assertIs(widget.parentWidget(), root.handle.widget)
            self.assertIsNone(widget.layout())
            self.assertEqual(geometry(widget), (x, 0, width, 24))
            x += width + 5
        self.assertEqual(root.children[1].handle.widget.value(), 40)
        self.assertEqual(root.children[2].handle.widget.currentText(), "Beta")

    def test_registered_custom_adapter_uses_sfles_native_port(self):
        from psx.core.vnode import create_element
        from psx.renderers.qt.pyqt import QtHandle

        calls = []
        def measure(widget, limits):
            calls.append("measure")
            return IntrinsicSizes(8, 23, 8, 15, 23, 15)
        def apply(widget, rect):
            calls.append(("apply", rect))
            widget.setGeometry(round(rect.x), round(rect.y),
                               round(rect.width), round(rect.height))
        def read(widget):
            calls.append("read")
            r = widget.geometry()
            return Rect(r.x(), r.y(), r.width(), r.height())

        class BadgeAdapter:
            sfle_port = SFLEExternalPort(measure, apply, read)

            def create(self, renderer, node, parent):
                return QtHandle("ParityBadge", qtwidgets.QLabel("Badge"))

            def update(self, renderer, handle, changed, removed):
                pass

            def destroy(self, renderer, handle):
                handle.widget.deleteLater()

            def bind_event(self, renderer, handle, event, slot):
                raise RendererCapabilityError("Unsupported external event.")

            def unbind_event(self, renderer, subscription):
                pass

        self.renderer.register_adapter("ParityBadge", BadgeAdapter())
        root = self.reconciler.render(Flex(
            create_element("ParityBadge", key="badge",
                           layout_width="42px", layout_height="18px",
                           flex_basis="42px", flex_shrink=0),
            width=160, height=80,
        ))
        widget = root.children[0].handle.widget
        self.assertIsInstance(widget, qtwidgets.QLabel)
        self.assertIs(widget.parentWidget(), root.handle.widget)
        self.assertEqual(geometry(widget), (0, 0, 42, 18))
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(0, 0, 42, 18)), calls)
        self.assertIn("read", calls)

    def test_missing_native_geometry_port_fails_before_factory(self):
        created = []
        def factory():
            created.append(True)
            return qtwidgets.QLabel()
        with self.assertRaisesRegex(RendererCapabilityError, "Native requires"):
            self.reconciler.render(Flex(
                Native(factory, renderer=BINDING,
                       layout_width="20px", layout_height="20px"),
                width=160, height=80,
            ))
        self.assertFalse(created)

    def test_unported_widget_still_rejected_and_default_flex_fail_closed(self):
        from psx import Image
        with self.assertRaisesRegex(RendererCapabilityError, "not certified"):
            self.reconciler.render(Flex(Image("unported.png"), width=160, height=80))
        legacy = RENDERER_CLASS(argv=["psx-qt-no-sfle"])
        second = Reconciler(legacy)
        with self.assertRaisesRegex(RendererCapabilityError, "F3-G2 SFLE geometry"):
            second.render(Flex(width=160, height=80))
        second.unmount()

    def test_stale_layout_generation_fails_before_native_write(self):
        class ForgedEngine:
            def compute(self, snapshot):
                valid = PythonLayoutEngine().compute(snapshot)
                return LayoutResult(1, snapshot.generation + 1, valid.boxes)

        self.renderer._sfle_engine = ForgedEngine()
        with self.assertRaises(SFLEError) as result:
            self.reconciler.render(Flex(
                button("B", "b", 40), width=160, height=80,
            ))
        self.assertEqual(result.exception.code, DiagnosticCode.INVALID_SNAPSHOT)
        self.assertIsNone(self.renderer.sfle_result)

    def test_wrong_thread_layout_commit_rejected(self):
        root = self.reconciler.render(Flex(
            button("B", "b", 40), width=160, height=80,
        ))
        errors = []
        def worker():
            try:
                self.renderer.commit_layout(root)
            except SFLEError as error:
                errors.append(error)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, DiagnosticCode.UNSUPPORTED_MEASUREMENT)


if __name__ == "__main__":
    unittest.main()
