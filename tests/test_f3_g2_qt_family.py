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

from psx import Button, Checkbox, Flex, Input, Native, ProgressBar, Text, TextArea, component, psx, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.f3_external import SFLEExternalPort
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, Rect, LayoutResult
from psx.sfle.native_pixel_space import DevicePixelSpace

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

    def test_qt_live_dpi_is_physical_only_not_double_applied_to_qwidget(self):
        root = self.reconciler.render(Flex(
            button("One", "one", 33),
            button("Two", "two", 25),
            direction="row", width="160px", height="80px",
            gap=7, align_items="flex-start",
        ))
        widget = root.handle.widget
        physical = DevicePixelSpace.from_widget("qt", widget)
        first, second = (n.handle.widget for n in root.children)
        self.assertEqual(geometry(first), (0, 0, 33, 20))
        self.assertEqual(geometry(second), (40, 0, 25, 20))
        # Qt 5 and Qt 6 still accept *logical QWidget units* at higher DPR.
        # QT_SCALE_FACTOR is set before importing Qt in a fresh CI process.
        if "QT_SCALE_FACTOR" in os.environ:
            self.assertGreaterEqual(physical.scale, 1.4)
        self.assertEqual(
            physical.to_physical(Rect(40, 0, 25, 20)).x,
            round(40 * physical.scale),
        )
        self.assertLessEqual(self.renderer._sfle_physical_commit_error,
                             physical.allowed_physical_error)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

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

    def test_multiline_text_remeasures_actual_post_flex_width(self):
        content = (
            "One two three four five six seven eight nine ten "
            "eleven twelve thirteen fourteen fifteen sixteen."
        )
        tree = self.reconciler.render(Flex(
            Text(content, key="copy", layout_width="100%", flex_shrink=0),
            button("Below", "below", 30),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        label = tree.children[0].handle.widget
        next_button = tree.children[1].handle.widget
        self.assertTrue(label.wordWrap())
        self.assertEqual(label.width(), 160)
        wide_height = label.height()
        wide_y = next_button.y()
        self.assertGreater(wide_height, 0)
        self.assertEqual(wide_y, wide_height)

        # Deliberately use the explicit live-viewport API to isolate the
        # measurement pass from any Qt platform window-manager resize event.
        self.renderer.set_sfle_constraints(viewport(90, 80))
        tree.handle.widget.resize(90, 80)
        self.renderer.commit_layout(tree)
        narrow_height = label.height()
        self.assertGreater(narrow_height, wide_height)
        self.assertEqual(label.width(), 90)
        self.assertEqual(next_button.y(), narrow_height)
        self.assertIs(tree.children[0].handle.widget, label)
        self.assertIs(tree.children[1].handle.widget, next_button)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

        self.renderer.set_sfle_constraints(viewport(160, 80))
        tree.handle.widget.resize(160, 80)
        self.renderer.commit_layout(tree)
        self.assertEqual(label.height(), wide_height)
        self.assertEqual(next_button.y(), wide_y)
        self.assertIs(tree.children[0].handle.widget, label)

    def test_textarea_auto_height_wraps_at_post_flex_width_without_remount(self):
        content = (
            "Alpha bravo charlie delta echo foxtrot golf hotel india juliet "
            "kilo lima mike november oscar papa quebec romeo sierra tango "
            "uniform victor whiskey xray yankee zulu."
        )
        changes = []
        root = self.reconciler.render(Flex(
            TextArea(
                value=content, key="editor", on_change=changes.append,
                layout_width="100%", flex_shrink=0,
            ),
            button("Below", "below", 45),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        editor = root.children[0].handle.widget
        below = root.children[1].handle.widget
        self.assertIsInstance(editor, qtwidgets.QPlainTextEdit)
        self.assertIsNone(editor.layout())
        self.assertIs(editor.parentWidget(), root.handle.widget)
        self.assertEqual(editor.toPlainText(), content)
        wide_height = editor.height()
        self.assertEqual(editor.width(), 160)
        self.assertEqual(below.y(), wide_height)

        gui = importlib.import_module(f"{PACKAGE}.QtGui")
        cursor = editor.textCursor()
        cursor.setPosition(3)
        cursor.setPosition(
            12, getattr(gui.QTextCursor, "MoveMode", gui.QTextCursor).KeepAnchor,
        )
        editor.setTextCursor(cursor)
        original_selection = (
            editor.textCursor().anchor(), editor.textCursor().position(),
        )
        root.handle.widget.show()
        self.renderer.application.processEvents()
        editor.setFocus()
        self.renderer.application.processEvents()
        self.assertTrue(editor.hasFocus())

        self.renderer.set_sfle_constraints(viewport(90, 300))
        root.handle.widget.resize(90, 300)
        self.renderer.commit_layout(root)
        narrow_height = editor.height()
        self.assertGreater(narrow_height, wide_height)
        self.assertEqual(editor.width(), 90)
        self.assertEqual(below.y(), narrow_height)
        self.assertEqual(editor.toPlainText(), content)
        self.assertEqual(
            (editor.textCursor().anchor(), editor.textCursor().position()),
            original_selection,
        )
        self.assertIs(root.children[0].handle.widget, editor)
        self.assertIs(root.children[1].handle.widget, below)
        self.assertTrue(editor.hasFocus())
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

        self.renderer.set_sfle_constraints(viewport(160, 300))
        root.handle.widget.resize(160, 300)
        self.renderer.commit_layout(root)
        self.assertEqual(editor.height(), wide_height)
        self.assertEqual(below.y(), wide_height)
        self.assertEqual(editor.toPlainText(), content)
        self.assertEqual(
            (editor.textCursor().anchor(), editor.textCursor().position()),
            original_selection,
        )
        self.assertEqual(changes, [])
        editor.insertPlainText("!")
        self.assertEqual(changes, [editor.toPlainText()])

    def test_textarea_native_edit_remeasures_without_reconciler_remount(self):
        self.renderer.set_sfle_constraints(viewport(160, 500))
        changes = []
        root = self.reconciler.render(Flex(
            TextArea(
                value="Short", key="editor", on_change=changes.append,
                layout_width="100%", flex_shrink=0,
            ),
            button("Below", "below", 45),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        editor = root.children[0].handle.widget
        below = root.children[1].handle.widget
        first_height = editor.height()
        previous_generation = self.renderer.sfle_result.generation
        editor.insertPlainText(" " + " ".join(["Multiline native editing"] * 14))
        self.assertEqual(len(changes), 1)
        self.renderer.application.processEvents()
        self.renderer.application.processEvents()
        self.assertIsNone(self.renderer._sfle_textarea_error)
        self.assertGreater(self.renderer.sfle_result.generation, previous_generation)
        self.assertGreater(editor.height(), first_height)
        self.assertEqual(below.y(), editor.height())
        self.assertIs(root.children[0].handle.widget, editor)
        self.assertEqual(editor.toPlainText(), changes[-1])

    def test_textarea_fixed_height_keeps_css_authority_and_rebinds_events(self):
        previous, current = [], []
        root = self.reconciler.render(Flex(
            TextArea(
                value="First value", key="editor", on_change=previous.append,
                layout_width="100%", layout_height="36px",
            ),
            button("Below", "below", 45),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        editor = root.children[0].handle.widget
        below = root.children[1].handle.widget
        self.assertEqual((editor.height(), below.y()), (36, 36))
        self.assertIsInstance(editor, qtwidgets.QPlainTextEdit)
        self.reconciler.render(Flex(
            TextArea(
                value="First value", key="editor", on_change=current.append,
                layout_width="100%", layout_height="36px",
            ),
            button("Below", "below", 45),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        self.assertIs(root.children[0].handle.widget, editor)
        self.renderer.set_sfle_constraints(viewport(90, 80))
        root.handle.widget.resize(90, 80)
        self.renderer.commit_layout(root)
        self.assertEqual((editor.width(), editor.height(), below.y()), (90, 36, 36))
        self.assertEqual((previous, current), ([], []))
        editor.insertPlainText("!")
        self.assertEqual(previous, [])
        self.assertEqual(current, [editor.toPlainText()])

    def test_native_root_resize_automatically_recomputes_sfle(self):
        class CountingEngine:
            def __init__(self):
                self.calls = 0
            def compute(self, snapshot):
                self.calls += 1
                return PythonLayoutEngine().compute(snapshot)

        engine = CountingEngine()
        self.renderer._sfle_engine = engine
        root = self.reconciler.render(Flex(
            button("Left", "left", 30),
            button("Right", "right", 20),
            direction="row", justify_content="space-between",
            width="100%", height="100%", align_items="flex-start",
        ))
        outer = root.handle.widget
        a, b = (child.handle.widget for child in root.children)
        self.assertEqual(engine.calls, 1)
        self.assertEqual((a.x(), b.x()), (0, 140))
        outer.show()
        self.renderer.application.processEvents()
        # Events originating from the toolkit's initial widget realization
        # must not replace the explicit viewport used for the first mount.
        self.assertEqual(self.renderer._sfle_constraints.width.value, 160)
        outer.resize(210, 100)
        outer.resize(260, 120)
        from time import sleep
        sleep(0.035)  # allow one 16ms native-frame debounce window
        self.renderer.application.processEvents()
        self.renderer.application.processEvents()
        self.assertIsNone(self.renderer._sfle_resize_error)
        self.assertEqual(
            (self.renderer._sfle_constraints.width.value,
             self.renderer._sfle_constraints.height.value), (260, 120),
        )
        self.assertEqual(engine.calls, 2)  # coalesced latest resize
        self.assertIs(root.children[0].handle.widget, a)
        self.assertIs(root.children[1].handle.widget, b)
        self.assertEqual((a.x(), b.x()), (0, 240))
        self.assertIsNone(outer.layout())
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1)

    def test_queued_resize_is_ignored_after_unmount(self):
        root = self.reconciler.render(Flex(
            button("A", "a", 30), width="100%", height="100%",
        ))
        outer = root.handle.widget
        outer.show()
        self.renderer.application.processEvents()
        outer.resize(230, 110)
        self.reconciler.unmount()
        from time import sleep
        sleep(0.035)
        self.renderer.application.processEvents()
        self.assertIsNone(self.renderer.sfle_result)
        self.assertIsNone(self.renderer._sfle_mounted_root)
        self.assertIsNone(self.renderer._sfle_watched_widget)

    def test_external_native_auto_height_uses_actual_assigned_width(self):
        widths = []

        def measure(widget, limits):
            width = limits.width.value
            widths.append(width)
            actual_height = 42 if width is not None and width <= 100 else 20
            return IntrinsicSizes(10, 240, actual_height, actual_height,
                                  240, actual_height)

        def apply(widget, rect):
            widget.setGeometry(
                round(rect.x), round(rect.y),
                round(rect.width), round(rect.height),
            )

        def read(widget):
            r = widget.geometry()
            return Rect(r.x(), r.y(), r.width(), r.height())

        root = self.reconciler.render(Flex(
            Native(
                qtwidgets.QLabel, renderer=BINDING,
                sfle_port=SFLEExternalPort(measure, apply, read),
                key="width-dependency", layout_width="100%", flex_shrink=0,
            ),
            button("After", "after", 35),
            direction="column", width="100%", height="100%",
            align_items="flex-start",
        ))
        leaf = root.children[0].handle.widget
        after = root.children[1].handle.widget
        self.assertEqual(geometry(leaf), (0, 0, 160, 20))
        self.assertEqual(after.y(), 20)
        self.assertIn(160, widths)

        self.renderer.set_sfle_constraints(viewport(90, 80))
        root.handle.widget.resize(90, 80)
        self.renderer.commit_layout(root)
        self.assertEqual(geometry(leaf), (0, 0, 90, 42))
        self.assertEqual(after.y(), 42)
        self.assertIn(90, widths)
        self.assertIs(root.children[0].handle.widget, leaf)

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
        progress = root.children[1].handle.widget
        # QProgressBar uses integer-scaled units for portable float precision.
        self.assertAlmostEqual(progress.value() / progress.maximum(), 0.4)
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

    def test_image_intrinsic_and_sfle_paint_survive_reconcile_resize(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from psx import Image

        gui = importlib.import_module(f"{PACKAGE}.QtGui")
        with TemporaryDirectory() as directory:
            source = str(Path(directory) / "image.png")
            pixmap = gui.QPixmap(24, 12)
            pixmap.fill(gui.QColor("#F03D64"))
            self.assertTrue(pixmap.save(source))
            root = self.reconciler.render(Flex(
                Image(source, key="picture", fit="contain"),
                Button("Below", key="below", layout_width="50px",
                       layout_height="20px", flex_basis="20px", flex_shrink=0),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            widget = root.children[0].handle.widget
            below = root.children[1].handle.widget
            self.assertIsInstance(widget, qtwidgets.QLabel)
            self.assertIsNone(widget.layout())
            self.assertIs(widget.parentWidget(), root.handle.widget)
            self.assertEqual(geometry(widget), (0, 0, 24, 12))
            self.assertEqual(below.y(), 12)
            self.assertEqual((widget.pixmap().width(), widget.pixmap().height()), (24, 12))
            self.assertNotEqual(widget.minimumSize().width(), 24)
            root = self.reconciler.render(Flex(
                Image(source, key="picture", fit="cover",
                      layout_width="60px", layout_height="28px"),
                Button("Below", key="below", layout_width="50px",
                       layout_height="20px", flex_basis="20px", flex_shrink=0),
                direction="column", width="100%", height="100%",
                align_items="flex-start",
            ))
            self.assertIs(root.children[0].handle.widget, widget)
            self.assertEqual(geometry(widget), (0, 0, 60, 28))
            self.assertEqual(below.y(), 28)
            self.assertEqual((widget.pixmap().width(), widget.pixmap().height()), (60, 28))
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_image_invalid_source_fails_intrinsic_measurement(self):
        from psx import Image
        with self.assertRaisesRegex(SFLEError, "intrinsic dimensions"):
            self.reconciler.render(Flex(
                Image("this-file-must-not-exist.png"), width=160, height=80,
            ))

    def test_unported_widget_still_rejected_and_default_flex_fail_closed(self):
        from psx import Switch
        with self.assertRaisesRegex(RendererCapabilityError, "not certified"):
            self.reconciler.render(Flex(Switch(), width=160, height=80))
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
