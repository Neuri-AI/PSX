from __future__ import annotations

import os
import sys
import threading
import unittest

# This must be set before the first Qt import so CI can run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "src")

from PySide6.QtWidgets import QLabel, QPushButton, QWidget
from pydux import Action, Store

from psx import App, Button, Column, Native, NativeWidget, Ref, Text, component, native_widget, psx, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.integrations.pydux import StoreProvider, use_selector
from psx.renderers.qt.pyside6 import PySide6Renderer, QtHandle


class PySide6RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.renderer = PySide6Renderer(argv=["psx-test"])

    def setUp(self) -> None:
        self.reconciler = Reconciler(self.renderer)

    def tearDown(self) -> None:
        self.reconciler.unmount()
        self.renderer.application.processEvents()

    def test_counter_update_reuses_qwidgets(self) -> None:
        calls: list[str] = []
        root = self.reconciler.render(
            Column(Text("Count: 1", key="count"), Button("+1", key="increment", on_click=lambda: calls.append("old")))
        )
        column = root.handle
        self.assertIsInstance(column, QtHandle)
        label_handle = root.children[0].handle
        button_handle = root.children[1].handle
        self.assertIsInstance(label_handle, QtHandle)
        self.assertIsInstance(button_handle, QtHandle)
        label = label_handle.widget
        button = button_handle.widget
        self.assertIsInstance(label, QLabel)
        self.assertIsInstance(button, QPushButton)

        self.reconciler.render(
            Column(Text("Count: 2", key="count"), Button("+1", key="increment", on_click=lambda: calls.append("new")))
        )

        self.assertIs(root.children[0].handle, label_handle)
        self.assertIs(root.children[1].handle, button_handle)
        self.assertIs(label_handle.widget, label)
        self.assertIs(button_handle.widget, button)
        self.assertEqual(label.text(), "Count: 2")
        button.click()
        self.assertEqual(calls, ["new"])

    def test_event_callback_replacement_keeps_one_qt_signal_connection(self) -> None:
        calls: list[str] = []
        self.reconciler.render(Button("Save", on_click=lambda: calls.append("old")))
        handle = self.reconciler.root.handle
        self.assertIsInstance(handle, QtHandle)
        button = handle.widget
        self.assertIsInstance(button, QPushButton)
        button.click()

        self.reconciler.render(Button("Save", on_click=lambda: calls.append("new")))
        button.click()
        self.assertEqual(calls, ["old", "new"])
        self.assertEqual(len(self.reconciler.root.event_slots), 1)

    def test_app_selects_pyside6_lazily(self) -> None:
        app = App(Column(Text("Hello")), renderer="pyside6")
        handle = app.mount()
        self.assertIsInstance(handle, QtHandle)
        app.unmount()

    def test_unknown_portable_prop_fails_instead_of_being_ignored(self) -> None:
        with self.assertRaises(RendererCapabilityError):
            self.reconciler.render(Text("Hello", font_size=14))

    def test_worker_state_update_is_committed_on_the_qt_event_loop(self) -> None:
        captured: dict[str, object] = {}

        @component
        def Counter():
            count, set_count = use_state(0)
            captured["set"] = set_count
            return Text(str(count))

        root = self.reconciler.render(Counter())
        label_handle = root.children[0].handle
        self.assertIsInstance(label_handle, QtHandle)
        label = label_handle.widget
        self.assertIsInstance(label, QLabel)
        worker = threading.Thread(target=lambda: captured["set"](1))
        worker.start()
        worker.join()
        self.assertEqual(label.text(), "0")
        self.renderer.application.processEvents()
        self.assertEqual(label.text(), "1")

    def test_worker_pydux_dispatch_is_committed_on_the_qt_event_loop(self) -> None:
        def reducer(state: int, action: Action) -> int:
            return state + 1 if action.type == "increment" else state

        store = Store(reducer, 0)

        @component
        def Counter():
            return Text(str(use_selector(lambda state: state)))

        root = self.reconciler.render(StoreProvider(store, Counter()))
        label_handle = root.children[0].children[0].handle
        self.assertIsInstance(label_handle, QtHandle)
        label = label_handle.widget
        self.assertIsInstance(label, QLabel)
        worker = threading.Thread(target=lambda: store.dispatch(Action("increment")))
        worker.start()
        worker.join()
        self.assertEqual(label.text(), "0")
        self.renderer.application.processEvents()
        self.assertEqual(label.text(), "1")

    def test_owned_native_widget_has_stable_identity_and_explicit_updates(self) -> None:
        updates: list[tuple[str, frozenset[str]]] = []

        def update(widget: object, changed: object, removed: frozenset[str]) -> None:
            self.assertIsInstance(widget, QLabel)
            assert isinstance(widget, QLabel)
            widget.setText(str(changed["message"]))
            updates.append((widget.text(), removed))

        native = NativeWidget(
            renderer="pyside6", factory=QLabel, update=update, name="StatusLabel"
        )
        root = self.reconciler.render(Column(native_widget(native, key="status", message="ready")))
        handle = root.children[0].handle
        self.assertIsInstance(handle, QtHandle)
        self.assertIsInstance(handle.widget, QLabel)
        self.assertEqual(handle.widget.text(), "ready")

        self.reconciler.render(Column(native_widget(native, key="status", message="updated")))
        self.assertIs(root.children[0].handle, handle)
        self.assertEqual(handle.widget.text(), "updated")
        self.assertEqual(updates, [("ready", frozenset()), ("updated", frozenset())])

    def test_borrowed_native_widget_is_not_deleted_and_parent_is_restored(self) -> None:
        original_parent = QWidget()
        borrowed = QLabel("borrowed", original_parent)
        native = NativeWidget(renderer="pyside6", widget=borrowed, ownership="borrowed")
        self.reconciler.render(Column(native_widget(native, key="borrowed")))
        self.assertIsNot(borrowed.parentWidget(), original_parent)

        self.reconciler.render(Column())
        self.assertIs(borrowed.parentWidget(), original_parent)
        self.assertEqual(borrowed.text(), "borrowed")

    def test_native_widget_rejects_implicit_prop_updates(self) -> None:
        native = NativeWidget(renderer="pyside6", factory=QLabel)
        with self.assertRaises(RendererCapabilityError):
            self.reconciler.render(native_widget(native, message="one"))

    def test_native_event_adapter_keeps_one_connection_when_callback_changes(self) -> None:
        connections: list[object] = []
        disconnections: list[object] = []

        def bind_event(widget: object, event: str, slot: object):
            self.assertEqual(event, "on_click")
            self.assertIsInstance(widget, QPushButton)
            button = widget

            def callback(_checked: bool = False) -> None:
                slot.invoke()  # type: ignore[union-attr]

            button.clicked.connect(callback)  # type: ignore[union-attr]
            connections.append(callback)

            def dispose() -> None:
                button.clicked.disconnect(callback)  # type: ignore[union-attr]
                disconnections.append(callback)

            return dispose

        native = NativeWidget(renderer="pyside6", factory=QPushButton, bind_event=bind_event)
        calls: list[str] = []
        self.reconciler.render(native_widget(native, on_click=lambda: calls.append("old")))
        handle = self.reconciler.root.handle
        self.assertIsInstance(handle, QtHandle)
        handle.widget.click()  # type: ignore[union-attr]
        self.reconciler.render(native_widget(native, on_click=lambda: calls.append("new")))
        handle.widget.click()  # type: ignore[union-attr]
        self.assertEqual(calls, ["old", "new"])
        self.assertEqual(len(connections), 1)
        self.reconciler.unmount()
        self.assertEqual(len(disconnections), 1)

    def test_native_factory_can_explicitly_receive_its_psx_parent(self) -> None:
        parents: list[object] = []

        def factory(parent: object) -> QLabel:
            parents.append(parent)
            return QLabel(parent)  # type: ignore[arg-type]

        native = NativeWidget(renderer="pyside6", factory=factory, takes_parent=True)
        self.reconciler.render(Column(native_widget(native)))
        handle = self.reconciler.root.children[0].handle
        self.assertIsInstance(handle, QtHandle)
        self.assertEqual(parents, [self.reconciler.root.handle.widget])
        self.assertIs(handle.widget.parentWidget(), self.reconciler.root.handle.widget)

    def test_native_facade_updates_qt_properties_without_recreating_widget(self) -> None:
        first = self.reconciler.render(Native(QLabel, props={"text": "one"}, key="label"))
        handle = first.handle
        self.assertIsInstance(handle, QtHandle)
        self.assertEqual(handle.widget.text(), "one")

        second = self.reconciler.render(Native(QLabel, props={"text": "two"}, key="label"))
        self.assertIs(second.handle, handle)
        self.assertEqual(handle.widget.text(), "two")

    def test_native_facade_maps_signals_and_exposes_widget_through_ref(self) -> None:
        calls: list[str] = []
        ref = Ref()
        self.reconciler.render(
            Native(QPushButton, props={"text": "Save"}, signals={"clicked": lambda: calls.append("clicked")}, ref=ref)
        )
        self.assertIsInstance(ref.current, QPushButton)
        ref.current.click()
        self.assertEqual(calls, ["clicked"])

    def test_native_tag_uses_the_same_facade(self) -> None:
        node = psx('<Native widget={QLabel} text={message} />', scope={"QLabel": QLabel, "message": "Markup"})
        self.reconciler.render(node)
        handle = self.reconciler.root.handle
        self.assertIsInstance(handle, QtHandle)
        self.assertEqual(handle.widget.text(), "Markup")


if __name__ == "__main__":
    unittest.main()
