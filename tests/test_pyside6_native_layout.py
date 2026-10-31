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

    def test_resizing_mixed_grid_reuses_text_hints_without_changing_native_geometry(self):
        """Mixed Grid reuse is committed only after Qt geometry readback."""
        self.renderer.set_sfle_constraints(constraints(420, 240))
        root = self.r.render(psx(
            '<div><Grid gap="8px">'
            '<GridItem span="6" key="a"><div>'
            '<div>Card A</div><div>Value 17</div>'
            '</div></GridItem>'
            '<GridItem span="6" key="b"><div>'
            '<div>Card B</div><div>Value 34</div>'
            '</div></GridItem>'
            '</Grid></div>'
        ))
        reuse = self.renderer._psx_grid_intrinsic_reuse
        initial_count = len(reuse)
        self.assertGreater(initial_count, 0)
        self.renderer.set_sfle_constraints(constraints(350, 240))
        self.renderer.commit_layout(root)
        # Wrapped labels legitimately acquire new width-specific entries
        # after a resize. Repeating the *same* width must reuse the newly
        # accepted measurements and preserve certified native geometry.
        resized_count = len(reuse)
        self.assertGreaterEqual(resized_count, initial_count)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)
        self.renderer.commit_layout(root)
        self.assertEqual(len(reuse), resized_count)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_css_background_paints_and_updates_in_place(self):
        first = self.r.render(psx('<div key="same" style="background-color: #112233" />'))
        widget = first.handle.widget
        self.assertIn("#112233", widget.styleSheet())
        changed = self.r.render(psx('<div key="same" style="background-color: #aabbcc" />'))
        self.assertIs(changed.handle.widget, widget)
        self.assertIn("#aabbcc", widget.styleSheet())
        self.r.render(psx('<div key="same" />'))
        self.assertEqual(widget.styleSheet(), "")

    def test_css_width_commits_to_qt_native_geometry(self):
        root = self.r.render(psx(
            '<div>'
            '<button style="width: 45px; height: 15px; margin-left: 3px; padding: 2px; border-width: 1px">Save</button></div>'
        ))
        self.assertEqual(root.children[0].handle.widget.width(), 51)
        self.assertEqual(root.children[0].handle.widget.height(), 21)
        self.assertEqual(root.children[0].handle.widget.x(), 3)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_html_block_commits_qt_rectangles_and_keyed_reorder(self):
        self.renderer.set_sfle_constraints(constraints(240, 140))
        original = self.r.render(psx(
            '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
        ))
        alpha, beta = (child.handle.widget for child in original.children)
        self.assertIsInstance(alpha, QPushButton)
        self.assertIsNone(original.handle.widget.layout())
        self.assertIs(alpha.parentWidget(), original.handle.widget)
        self.assertLess(alpha.width(), 240)
        self.assertLess(beta.width(), 240)
        self.assertEqual(alpha.y(), 0)
        self.assertEqual(beta.y(), 0)
        self.assertEqual(beta.x(), alpha.width())
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

        reordered = self.r.render(psx(
            '<div><button key="b">Beta</button><button key="a">Alpha</button></div>'
        ))
        self.assertIs(reordered.children[0].handle.widget, beta)
        self.assertIs(reordered.children[1].handle.widget, alpha)
        self.assertEqual(beta.y(), 0)
        self.assertEqual(alpha.y(), 0)
        self.assertEqual(alpha.x(), beta.width())
        self.assertIsNone(original.handle.widget.layout())

    def test_centered_flex_paragraph_uses_full_block_width_and_wrap_height(self):
        """Block h1/p fill the root, but button remains intrinsic and centered."""
        self.renderer.set_sfle_constraints(constraints(800, 600))
        label = "Edit src/App.tsx and save to test HMR"
        root = self.r.render(psx(
            '<div style="display: flex; flex-direction: column; '
            'gap: 16px; justify-content: center; align-items: center; '
            'height: 100vh">'
            '<h1>Get started</h1>'
            '<p style="background-color: red">'
            + label +
            '</p><button>Count is 0</button></div>'
        ))
        heading, paragraph, button = root.children
        text = paragraph.children[0].handle.widget
        title = heading.children[0].handle.widget
        for block in (heading, paragraph):
            self.assertAlmostEqual(block.handle.widget.width(), 800, delta=1)
        self.assertGreaterEqual(text.width(), 798)
        self.assertGreaterEqual(title.width(), 798)
        self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()) - 1)
        self.assertGreaterEqual(title.height(), title.heightForWidth(title.width()) - 1)
        self.assertIn("background", paragraph.handle.widget.styleSheet().lower())
        self.assertLess(button.handle.widget.width(), 800)
        self.assertGreaterEqual(button.handle.widget.y(),
                                paragraph.handle.widget.y() + paragraph.handle.widget.height())
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

        for width in (320, 140, 800):
            self.renderer.set_sfle_constraints(constraints(width, 600))
            self.renderer.commit_layout(root)
            for block in (heading, paragraph):
                self.assertAlmostEqual(block.handle.widget.width(), width, delta=1)
            # Reflow must increase automatic height, not clip glyphs inside
            # the background or overlap the next flex sibling.
            self.assertGreaterEqual(text.height(), text.heightForWidth(text.width()) - 1)
            self.assertGreaterEqual(title.height(), title.heightForWidth(title.width()) - 1)
            self.assertGreaterEqual(paragraph.handle.widget.height(), text.height() - 1)
            self.assertGreaterEqual(heading.handle.widget.height(), title.height() - 1)
            self.assertGreaterEqual(
                button.handle.widget.y(),
                paragraph.handle.widget.y() + paragraph.handle.widget.height(),
            )
            self.assertLess(button.handle.widget.width(), width)
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_mixed_inline_span_remains_in_paragraph_text_line(self):
        self.renderer.set_sfle_constraints(constraints(800, 400))
        root = self.r.render(psx(
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
        assert paragraph.handle.widget.width() == 800
        assert prefix.y() == span.y() == suffix.y()
        assert prefix.x() < span.x() < suffix.x()
        assert nested.text() == "src/App.tsx"
        assert span.width() >= nested.width() - 1
        assert button.handle.widget.y() >= (
            paragraph.handle.widget.y() + paragraph.handle.widget.height()
        )
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

        # The sentence is one inline run; resizing may wrap words but must
        # never split solely at the <span> element boundary.
        for width in (220, 800):
            self.renderer.set_sfle_constraints(constraints(width, 400))
            self.renderer.commit_layout(root)
            assert abs(paragraph.handle.widget.width() - width) <= 1
            assert paragraph.handle.widget.height() >= prefix.height()
            assert button.handle.widget.y() >= (
                paragraph.handle.widget.y() + paragraph.handle.widget.height()
            )
            self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_nested_html_headings_paragraphs_and_inline_text_use_native_flow(self):
        self.renderer.set_sfle_constraints(constraints(320, 200))
        root = self.r.render(psx(
            "<div>"
            "<h1>Hello Velto!</h1>"
            "<p>Native UI with web-like layout.</p>"
            "<span>First second third fourth</span>"
            "<button>Continue</button>"
            "</div>"
        ))
        heading, paragraph, inline, button = root.children
        self.assertIsNone(root.handle.widget.layout())
        self.assertIsInstance(heading.children[0].handle.widget, QLabel)
        self.assertIsInstance(paragraph.children[0].handle.widget, QLabel)
        self.assertEqual(heading.handle.widget.y(), 0)
        self.assertEqual(paragraph.handle.widget.y(), heading.handle.widget.height())
        self.assertGreaterEqual(inline.handle.widget.y(),
                                paragraph.handle.widget.y() + paragraph.handle.widget.height())
        self.assertTrue(
            button.handle.widget.x() >= inline.handle.widget.x() + inline.handle.widget.width()
            or button.handle.widget.y() >= inline.handle.widget.y() + inline.handle.widget.height()
        )
        self.assertLess(button.handle.widget.width(), 320)
        self.assertGreater(inline.handle.widget.height(), 0)
        self.assertLessEqual(self.renderer.sfle_result.geometry_commit_error, 1.0)

    def test_scroll_unmount_releases_native_viewport(self):
        from psx import Scroll
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
        self.assertTrue(area._psx_sfle_scroll)
        self.r.unmount()
        self.renderer.application.processEvents()
        self.assertIsNone(area.parentWidget())
        self.assertFalse(area._fade.isActive())

    def test_scroll_disabled_axes_reset_existing_offsets(self):
        from psx import Scroll
        from psx.sfle.model import Rect
        from psx.sfle.native_scroll_hosts import apply_qt_scroll, binding_from_host
        from psx.sfle.scroll_offsets import ScrollOffset
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
        binding = binding_from_host(area._psx_props, Rect(0, 0, 120, 80),
                                    Rect(0, 0, 300, 200))
        apply_qt_scroll(area, binding, ScrollOffset(60, 45))
        self.assertEqual((area.horizontalScrollBar().value(),
                          area.verticalScrollBar().value()), (60, 45))
        area._psx_props = {**area._psx_props, "direction": "horizontal"}
        restricted = binding_from_host(area._psx_props, Rect(0, 0, 120, 80),
                                       Rect(0, 0, 300, 200))
        apply_qt_scroll(area, restricted, ScrollOffset(60, 45))
        self.assertEqual((area.horizontalScrollBar().value(),
                          area.verticalScrollBar().value()), (60, 0))

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

    def test_nested_qt_scroll_residual_routes_to_parent_once(self):
        from psx import Scroll
        self.renderer.set_sfle_constraints(constraints(300, 300))
        root = self.r.render(Flex(
            Scroll(Flex(
                Scroll(Flex(item("Inside", "inside", 40),
                            width="300px", height="300px",
                            key="inner-content", direction="row",
                            align_items="flex-start"),
                       direction="vertical", key="inner",
                       layout_width="120px", layout_height="80px",
                       flex_basis="120px", flex_shrink=0),
                width="300px", height="300px",
                key="outer-content", direction="column",
                align_items="flex-start"),
                direction="vertical", key="outer",
                layout_width="160px", layout_height="100px",
                flex_basis="160px", flex_shrink=0),
            direction="row", width="300px", height="300px",
            align_items="flex-start",
        ))
        outer = root.children[0].handle.widget
        inner = root.children[0].children[0].children[0].handle.widget
        assert inner._psx_sfle_scroll and outer._psx_sfle_scroll
        assert inner.parentWidget() is outer._psx_content or (
            inner.parentWidget().parentWidget() is outer._psx_content
        )
        inner.verticalScrollBar().setValue(inner.verticalScrollBar().maximum())
        outer.verticalScrollBar().setValue(0)
        from PySide6.QtCore import Qt, QPoint, QPointF
        from PySide6.QtGui import QWheelEvent
        wheel = QWheelEvent(
            QPointF(20, 20), QPointF(20, 20), QPoint(0, 0),
            QPoint(0, -120), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate, False,
        )
        inner.wheelEvent(wheel)
        self.assertTrue(wheel.isAccepted())
        self.assertEqual(outer.verticalScrollBar().value(), 48)
        self.assertEqual(inner.verticalScrollBar().value(),
                         inner.verticalScrollBar().maximum())

    def test_scroll_failed_native_commit_restores_offsets_and_extent(self):
        from unittest.mock import patch
        from psx import Scroll
        from psx.sfle import native_scroll_hosts

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
        area.horizontalScrollBar().setValue(60)
        area.verticalScrollBar().setValue(30)
        before_size = (area._psx_content.width(), area._psx_content.height())
        original = native_scroll_hosts.apply_qt_scroll

        def fail_after_mutation(area, binding, offset):
            original(area, binding, offset)
            area.horizontalScrollBar().setValue(0)
            area.verticalScrollBar().setValue(0)
            raise RuntimeError("injected native viewport failure")

        with patch.object(native_scroll_hosts, "apply_qt_scroll",
                          side_effect=fail_after_mutation):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.renderer.commit_layout(root)
        self.assertEqual((area.horizontalScrollBar().value(),
                          area.verticalScrollBar().value()), (60, 30))
        self.assertEqual((area._psx_content.width(),
                          area._psx_content.height()), before_size)

    def test_scroll_reflow_preserves_native_offset_focus_and_widget_identity(self):
        from psx import Scroll
        from PySide6.QtWidgets import QApplication
        self.renderer.set_sfle_constraints(constraints(300, 200))
        root = self.r.render(Flex(
            Scroll(Flex(item("Focused", "focused", 40),
                        direction="row", width="300px", height="200px",
                        key="content", align_items="flex-start"),
                   direction="both", key="scroll",
                   layout_width="120px", layout_height="80px",
                   flex_basis="120px", flex_shrink=0),
            direction="row", width="300px", height="200px",
            align_items="flex-start",
        ))
        scroll = root.children[0].handle.widget
        button = root.children[0].children[0].children[0].handle.widget
        scroll.horizontalScrollBar().setValue(70)
        scroll.verticalScrollBar().setValue(40)
        button.setFocus()
        initial_focus = QApplication.focusWidget()
        self.renderer.commit_layout(root)
        self.assertEqual((scroll.horizontalScrollBar().value(),
                          scroll.verticalScrollBar().value()), (70, 40))
        self.assertIs(root.children[0].children[0].children[0].handle.widget, button)
        self.assertIs(QApplication.focusWidget(), initial_focus)
        self.renderer.set_sfle_constraints(constraints(300, 200))
        self.renderer.commit_layout(root)
        self.assertEqual((scroll.horizontalScrollBar().value(),
                          scroll.verticalScrollBar().value()), (70, 40))

    def test_native_scroll_keyboard_moves_and_releases_at_boundary(self):
        from psx import Scroll
        from PySide6.QtCore import Qt, QEvent
        from PySide6.QtGui import QKeyEvent
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
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down,
                          Qt.KeyboardModifier.NoModifier)
        area.keyPressEvent(event)
        self.assertEqual(area.verticalScrollBar().value(), 40)
        self.assertTrue(event.isAccepted())
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down,
                          Qt.KeyboardModifier.NoModifier)
        area.keyPressEvent(event)
        self.assertFalse(event.isAccepted())

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
                      gap="6" align_items="flex-start">
                    <Button label="A" key="a" layout_width="30px"
                            layout_height="15px" flex_basis="30px" flex_shrink="0" />
                    <Button label="B" key="b" layout_width="20px"
                            layout_height="15px" flex_basis="20px" flex_shrink="0" />
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

    def test_qt_css_text_intrinsic_hint_cache_preserves_wrapping_and_invalidation(self):
        root = self.r.render(Flex(
            Text("A long intrinsic label with several words for native Qt sizing"),
            width="100%", height="100%",
        ))
        widget = root.children[0].handle.widget
        widget._psx_sync_line_height(26)
        document = widget._psx_css_document
        self.assertIsNotNone(document)
        initial_hint = widget.sizeHint()
        cached = widget._psx_css_intrinsic_hint
        self.assertIsNotNone(cached)

        # A later paint/height-for-width calculation may leave QTextDocument
        # constrained. Intrinsic sizeHint must retain its unwrapped value.
        document.setTextWidth(36)
        widget.heightForWidth(36)
        self.assertEqual(widget.sizeHint(), initial_hint)
        self.assertIs(widget._psx_css_intrinsic_hint, cached)
        self.assertEqual(widget.sizeHint(), initial_hint)

        # Native document edits and explicit style changes both invalidate.
        document.setPlainText("A changed label text with different width")
        widget.sizeHint()
        self.assertIsNot(widget._psx_css_intrinsic_hint, cached)
        widget._psx_sync_line_height(30)
        self.assertIsNone(widget._psx_css_intrinsic_hint)
        self.assertIsNotNone(widget.sizeHint())

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
        from psx.core.registry import builtin_component_registry
        self.assertFalse(builtin_component_registry().contains("Row"))

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


def test_html_flow_public_native_geometry_receipt_pyside6(request):
    from tests.certification.public_behavior_census import Feature, assert_feature
    renderer = PySide6Renderer(
        argv=["psx-block-public-census"],
        sfle_constraints=constraints(220, 120),
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx(
            "<div><button>First</button><button>Second</button></div>"
        ))
        first, second = (child.handle.widget for child in root.children)
        assert_feature(
            request, Feature("div", "pyside6", "interaction", "semantic_flow",
                             "native_geometry", applicability="partial_native"),
            0 < first.width() < 220
            and 0 < second.width() < 220
            and first.y() == second.y() == 0
            and second.x() == first.width()
            and root.handle.widget.layout() is None,
        )
    finally:
        reconciler.unmount()
        renderer.application.processEvents()
