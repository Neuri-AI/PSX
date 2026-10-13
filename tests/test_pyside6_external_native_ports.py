"""Native SFLE real PySide6 external Native/custom leaf SFLE port certification."""
from __future__ import annotations

import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel

from psx import Flex, Text
from psx.core.native import Native
from psx.core.vnode import create_element
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyqt import QtHandle
from psx.renderers.qt.pyside import PySide6Renderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.external_native_geometry_ports import SFLEExternalPort
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, Rect,
)


def constraints():
    return LayoutConstraints(AvailableSize(160, True), AvailableSize(80, True))


def external_port(calls=None, *, read_offset=0):
    calls = [] if calls is None else calls
    def measure(widget, limits):
        assert limits == constraints()
        calls.append("measure")
        return IntrinsicSizes(12, 22, 8, 16, 22, 16)
    def apply(widget, rect):
        calls.append(("apply", rect))
        widget.setGeometry(round(rect.x), round(rect.y),
                           round(rect.width), round(rect.height))
    def read(widget):
        calls.append("read")
        r = widget.geometry()
        return Rect(r.x() + read_offset, r.y(), r.width(), r.height())
    return SFLEExternalPort(measure, apply, read)


class QtExternalPortTests(unittest.TestCase):
    def setUp(self):
        self.renderer = PySide6Renderer(
            argv=["psx-sfle-native"], sfle_constraints=constraints(),
            engine=PythonLayoutEngine(),
        )
        self.tree = Reconciler(self.renderer)

    def tearDown(self):
        self.tree.unmount()
        self.renderer.application.processEvents()

    def test_native_qwidget_receives_exact_projected_geometry_with_three_hooks(self):
        calls = []
        native = Native(QLabel, renderer="pyside6", sfle_port=external_port(calls),
                        key="native", layout_width="35px",
                        layout_height="18px", flex_basis="35px", flex_shrink=0)
        root = self.tree.render(Flex(
            Text("Leading", key="label", layout_width="20px",
                 layout_height="18px", flex_basis="20px", flex_shrink=0),
            native, width=160, height=80, gap=7,
            align_items="flex-start",
        ))
        widget = root.children[1].handle.widget
        self.assertIsInstance(widget, QLabel)
        self.assertIs(widget.parentWidget(), root.handle.widget)
        self.assertEqual((widget.x(), widget.y(), widget.width(), widget.height()),
                         (27, 0, 35, 18))
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(27, 0, 35, 18)), calls)
        self.assertIn("read", calls)
        self.assertEqual(self.renderer.sfle_result.geometry_commit_error, 0.0)

    def test_missing_native_port_fails_before_widget_factory(self):
        calls = []
        def factory():
            calls.append("created")
            return QLabel()
        with self.assertRaisesRegex(RendererCapabilityError, "Native requires"):
            self.tree.render(Flex(
                Native(factory, renderer="pyside6",
                       layout_width="20px", layout_height="20px"),
                width=160, height=80,
            ))
        self.assertEqual(calls, [])

    def test_registered_custom_host_adapter_is_measured_and_committed(self):
        calls = []
        class CustomAdapter:
            sfle_port = external_port(calls)
            def create(self, renderer, node, parent):
                return QtHandle("CustomBadge", QLabel("Badge"))
            def update(self, renderer, handle, changed, removed):
                pass
            def destroy(self, renderer, handle):
                handle.widget.deleteLater()
            def bind_event(self, renderer, handle, event, slot):
                raise RendererCapabilityError("Unsupported custom event.")
            def unbind_event(self, renderer, subscription):
                pass

        self.renderer.register_adapter("CustomBadge", CustomAdapter())
        root = self.tree.render(Flex(
            create_element("CustomBadge", key="badge", layout_width="42px",
                           layout_height="18px", flex_basis="42px", flex_shrink=0),
            width=160, height=80,
        ))
        widget = root.children[0].handle.widget
        self.assertIsInstance(widget, QLabel)
        self.assertIs(widget.parentWidget(), root.handle.widget)
        self.assertEqual((widget.x(), widget.y(), widget.width(), widget.height()),
                         (0, 0, 42, 18))
        self.assertIn("measure", calls)
        self.assertIn(("apply", Rect(0, 0, 42, 18)), calls)
        self.assertIn("read", calls)

    def test_registered_custom_host_without_port_fails_before_factory(self):
        calls = []
        class WithoutPort:
            def create(self, renderer, node, parent):
                calls.append("created")
                return QtHandle("Opaque", QLabel())
        self.renderer.register_adapter("Opaque", WithoutPort())
        with self.assertRaisesRegex(RendererCapabilityError, "requires sfle_port"):
            self.tree.render(Flex(create_element("Opaque"), width=160, height=80))
        self.assertEqual(calls, [])

    def test_wrong_native_readback_rolls_back_real_geometry(self):
        calls = []
        bad = external_port(calls, read_offset=3)
        native = Native(QLabel, renderer="pyside6", sfle_port=bad,
                        layout_width="30px", layout_height="14px",
                        flex_basis="30px", flex_shrink=0)
        with self.assertRaisesRegex(SFLEError, "readback exceeds"):
            self.tree.render(Flex(native, width=160, height=80))
        self.assertTrue(any(
            isinstance(entry, tuple) and entry[0] == "apply" for entry in calls
        ))
        self.assertIsNone(self.renderer.sfle_result)

    def test_borrowed_native_qwidget_preserves_caller_ownership_and_parent(self):
        from psx.core.native import NativeWidget, NativeOwnership
        from psx.core.vnode import native_widget
        from psx.sfle.native_operation_oracles import Observation, ORACLES

        parent = QLabel()
        widget = QLabel(parent)
        prior_parent = widget.parentWidget()
        deleted = []
        widget.destroyed.connect(lambda *_: deleted.append(True))
        calls = []
        declaration = NativeWidget(
            renderer="pyside6", widget=widget,
            ownership=NativeOwnership.BORROWED,
            update=lambda w, changed, removed: (
                calls.append(("update", dict(changed), removed)),
                w.setText(changed["text"]) if "text" in changed else None,
            ),
            sfle_port=external_port(),
        )
        def view(label):
            return Flex(native_widget(
                declaration, key="external", text=label,
                layout_width="45px", layout_height="20px",
                flex_basis="45px", flex_shrink=0,
            ), width=160, height=80, align_items="flex-start")

        root = self.tree.render(view("Before"))
        self.assertIs(root.children[0].handle.widget, widget)
        self.assertEqual(widget.text(), "Before")
        self.assertIsNotNone(widget.parentWidget())
        updated = self.tree.render(view("After"))
        self.assertIs(updated.children[0].handle.widget, widget)
        self.assertEqual(widget.text(), "After")
        before = Observation(id(widget), True, (0, 0, 45, 20), owner="caller")
        self.tree.unmount()
        self.renderer.application.processEvents()
        after = Observation(id(widget), False, (0, 0, 45, 20), owner="caller",
                            disposed=bool(deleted))
        ORACLES["borrowed_ownership"](before, after)
        self.assertIs(widget.parentWidget(), prior_parent)
        self.assertFalse(deleted)
        self.assertEqual(len([c for c in calls if c[0] == "update"]), 2)
        widget.setText("Caller still owns this")
        self.assertEqual(widget.text(), "Caller still owns this")
        parent.deleteLater()

