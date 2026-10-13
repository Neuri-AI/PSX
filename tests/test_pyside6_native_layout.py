"""Native SFLE Qt integration: SFLE is the *only* Flex geometry authority."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel, QPushButton

from psx import Button, Flex, Text, component, use_state, psx
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutResult


def constraints(width=160, height=80):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))


def item(label, key, width):
    return Button(label, key=key, layout_width=f"{width}px", layout_height="20px",
                  flex_basis=f"{width}px", flex_shrink=0)


class QtSFLEGeometryTests(unittest.TestCase):
    def setUp(self):
        self.renderer = PySide6Renderer(
            argv=["psx-sfle-qt"], sfle_constraints=constraints(),
            engine=PythonLayoutEngine(),
        )
        self.r = Reconciler(self.renderer)

    def tearDown(self):
        self.r.unmount()
        self.renderer.application.processEvents()

    def test_native_scroll_overflow_offsets_and_viewport_clipping(self):
        from psx import Scroll
        from psx.sfle.native_scroll_hosts import apply_qt_scroll, binding_from_host
        from psx.sfle.scroll_offsets import ScrollOffset
        from psx.sfle.model import Rect

        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.r.render(Flex(
            Scroll(Flex(item("Inside", "inside", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        area = root.children[0].handle.widget
        content = root.children[0].children[0].handle.widget
        self.assertIs(content.parentWidget(), area._psx_content)
        self.assertEqual((area._psx_content.width(), area._psx_content.height()), (300, 200))
        self.assertEqual((content.x(), content.y(), content.width(), content.height()), (0, 0, 300, 200))
        self.assertIsNone(content.layout())
        binding = binding_from_host(area._psx_props, Rect(0, 0, 120, 80),
                                    Rect(0, 0, 300, 200))
        result = apply_qt_scroll(area, binding, ScrollOffset(90, 60))
        self.assertEqual(result.offset, ScrollOffset(90, 60))
        self.assertEqual((area.horizontalScrollBar().value(),
                          area.verticalScrollBar().value()), (90, 60))
        self.assertEqual((area.horizontalScrollBar().maximum(),
                          area.verticalScrollBar().maximum()), (180, 120))
        apply_qt_scroll(area, binding, ScrollOffset(999, 999))
        self.assertEqual((area.horizontalScrollBar().value(),
                          area.verticalScrollBar().value()), (180, 120))
        self.assertIs(area.viewport(), area._psx_content.parentWidget())

    def test_real_qwidgets_take_exact_sfle_geometry_without_qboxlayout(self):
        root = self.r.render(
            Flex(
                Text("Left", key="left", layout_width="40px", layout_height="20px",
                     flex_basis="40px", flex_shrink=0),
                item("Right", "right", 30),
                direction="row", gap=8, width="160px", height="80px",
                align_items="flex-start",
            )
        )
        assert root.handle.widget.layout() is None
        label, button = (child.handle.widget for child in root.children)
        assert isinstance(label, QLabel) and isinstance(button, QPushButton)
        assert label.parentWidget() is root.handle.widget
        assert button.parentWidget() is root.handle.widget
        self.assertEqual((label.x(), label.y(), label.width(), label.height()), (0, 0, 40, 20))
        self.assertEqual((button.x(), button.y(), button.width(), button.height()), (48, 0, 30, 20))
        self.assertEqual(self.renderer.sfle_result.geometry_commit_error, 0.0)
        self.assertEqual(len(self.renderer.sfle_result.boxes), 3)

    def test_markup_builder_real_qt_and_nested_parent_relative_coordinates(self):
        root = self.r.render(psx("""
            <Flex direction="column" width="160px" height="80px"
                  align_items="flex-start">
                <Flex direction="row" width="120px" height="40px"
                      gap={6} align_items="flex-start">
                    <Button label="A" key="a" layout_width="30px"
                            layout_height="15px" flex_basis="30px" flex_shrink={0} />
                    <Button label="B" key="b" layout_width="20px"
                            layout_height="15px" flex_basis="20px" flex_shrink={0} />
                </Flex>
            </Flex>
        """))
        inner = root.children[0].handle.widget
        a, b = (child.handle.widget for child in root.children[0].children)
        assert inner.layout() is None
        assert a.parentWidget() is inner and b.parentWidget() is inner
        self.assertEqual((a.x(), a.y(), a.width(), a.height()), (0, 0, 30, 15))
        self.assertEqual((b.x(), b.y(), b.width(), b.height()), (36, 0, 20, 15))

    def test_keyed_reorder_uses_existing_widgets_and_recomputes_only_sfle(self):
        before = self.r.render(Flex(item("A", "a", 30), item("B", "b", 20),
                                    width=160, height=80, gap=4,
                                    align_items="flex-start"))
        a, b = (child.handle.widget for child in before.children)
        self.assertLess(a.x(), b.x())
        after = self.r.render(Flex(item("B", "b", 20), item("A", "a", 30),
                                   width=160, height=80, gap=9,
                                   align_items="flex-start"))
        self.assertIs(after.children[0].handle.widget, b)
        self.assertIs(after.children[1].handle.widget, a)
        self.assertEqual((b.x(), a.x()), (0, 29))
        self.assertEqual(self.renderer.sfle_result.generation, 2)
        self.assertIsNone(after.handle.widget.layout())

    def test_live_state_and_event_subscription_survive_flex_relayout(self):
        setters = []
        events = []

        @component
        def Counter():
            number, set_number = use_state(0)
            setters.append(set_number)
            return Flex(
                Button("Tap", on_click=lambda: events.append(number), key="button",
                       layout_width=f"{20 + number * 10}px", layout_height="20px",
                       flex_basis=f"{20 + number * 10}px", flex_shrink=0),
                width="160px", height="80px",
            )

        root = self.r.render(Counter())
        handle = root.children[0].children[0].handle
        button = handle.widget
        button.click()
        self.assertEqual(events, [0])
        setters[-1](2)
        self.renderer.application.processEvents()
        self.assertIs(root.children[0].children[0].handle, handle)
        self.assertEqual(button.width(), 40)
        button.click()
        self.assertEqual(events, [0, 2])

    def test_viewport_resize_recommits_without_remount(self):
        root = self.r.render(Flex(
            item("A", "a", 30), width="100%", height="100%", gap=4,
            align_items="flex-start",
        ))
        widget = root.children[0].handle.widget
        first = self.renderer.sfle_result.generation
        self.renderer.set_sfle_constraints(constraints(300, 120))
        self.renderer.commit_layout(root)
        self.assertIs(root.children[0].handle.widget, widget)
        self.assertGreater(self.renderer.sfle_result.generation, first)
        self.assertIsNone(root.handle.widget.layout())

    def test_unported_component_is_explicitly_rejected(self):
        from psx import Row
        with self.assertRaisesRegex(RendererCapabilityError, "not certified"):
            self.r.render(Flex(Row(), width=160, height=80))

    def test_additional_qt_native_primitives_have_sfle_geometry_and_no_qboxlayout(self):
        from psx import Checkbox, Input, Slider, ProgressBar, Radio, Select
        from PySide6.QtWidgets import (
            QCheckBox, QLineEdit, QSlider, QProgressBar, QRadioButton, QComboBox,
        )
        specs = [
            (Checkbox(checked=True, key="cb", layout_width="24px",
                      layout_height="30px", flex_basis="24px", flex_shrink=0), QCheckBox, 24),
            (Input(value="hello", key="entry", layout_width="92px",
                   layout_height="30px", flex_basis="92px", flex_shrink=0), QLineEdit, 92),
            (Slider(value=25, key="slider", layout_width="100px",
                    layout_height="30px", flex_basis="100px", flex_shrink=0), QSlider, 100),
            (ProgressBar(value=40, key="progress", layout_width="110px",
                         layout_height="30px", flex_basis="110px", flex_shrink=0), QProgressBar, 110),
            (Radio("r", label="Pick", key="radio", layout_width="70px",
                   layout_height="30px", flex_basis="70px", flex_shrink=0), QRadioButton, 70),
            (Select(options=["Alpha", "Beta"], value="Beta", key="select",
                    layout_width="100px", layout_height="30px",
                    flex_basis="100px", flex_shrink=0), QComboBox, 100),
        ]
        root = self.r.render(Flex(
            *(node for node, _, _ in specs),
            width="700px", height="80px", direction="row", gap=6,
            align_items="flex-start",
        ))
        x = 0
        for (node, expected_type, width), instance in zip(specs, root.children):
            widget = instance.handle.widget
            self.assertIsInstance(widget, expected_type)
            self.assertIs(widget.parentWidget(), root.handle.widget)
            self.assertIsNone(widget.layout(), node.type)
            self.assertEqual(
                (widget.x(), widget.y(), widget.width(), widget.height()),
                (x, 0, width, 30), node.type,
            )
            x += width + 6
        self.assertEqual(len(self.renderer.sfle_result.boxes), 7)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)
        self.assertTrue(root.children[0].handle.widget.isChecked())
        self.assertEqual(root.children[1].handle.widget.text(), "hello")
        self.assertEqual(root.children[5].handle.widget.currentText(), "Beta")

    def test_qt_checkbox_event_and_state_reconciliation_in_sfle_tree(self):
        from psx import Checkbox
        calls = []
        root = self.r.render(Flex(
            Checkbox(checked=False, key="cb", on_change=calls.append,
                     layout_width="40px", layout_height="24px",
                     flex_basis="40px", flex_shrink=0),
            width=160, height=80,
        ))
        native = root.children[0].handle.widget
        native.click()
        self.assertEqual(calls, [True])
        after = self.r.render(Flex(
            Checkbox(checked=True, key="cb", on_change=calls.append,
                     layout_width="60px", layout_height="24px",
                     flex_basis="60px", flex_shrink=0),
            width=160, height=80,
        ))
        self.assertIs(after.children[0].handle.widget, native)
        self.assertEqual(native.width(), 60)
        self.assertTrue(native.isChecked())
        self.assertEqual(calls, [True])

    def test_engine_generation_forgery_never_commits_geometry(self):
        class WrongEngine:
            def compute(self, request):
                output = PythonLayoutEngine().compute(request)
                return LayoutResult(1, request.generation + 1, output.boxes)

        self.renderer._sfle_engine = WrongEngine()
        with self.assertRaises(SFLEError) as raised:
            self.r.render(Flex(item("A", "a", 30), width=160, height=80))
        self.assertEqual(raised.exception.code, DiagnosticCode.INVALID_SNAPSHOT)
        self.assertIsNone(self.renderer.sfle_result)

    def test_default_renderer_still_fails_closed_without_sfle_viewport(self):
        regular = PySide6Renderer(argv=["psx-qt-no-fallback"])
        r = Reconciler(regular)
        with self.assertRaisesRegex(RendererCapabilityError, "Native SFLE SFLE geometry"):
            r.render(Flex(width=160, height=80))
        r.unmount()
