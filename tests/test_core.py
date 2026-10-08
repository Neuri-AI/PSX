from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from psx import Button, Column, DuplicateKeyError, InvalidChildError, Row, Text, component
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = HeadlessRenderer()
        self.reconciler = Reconciler(self.renderer)

    def test_normalizes_supported_children_and_rejects_true(self) -> None:
        node = Column("a", 2, None, False, [Text("b")])
        self.assertEqual([child.props["value"] for child in node.children], ["a", "2", "b"])
        with self.assertRaises(InvalidChildError):
            Column(True)

    def test_prop_update_preserves_existing_handle(self) -> None:
        root = self.reconciler.render(Column(Text("one"), Button("Save")))
        column = root.handle
        text, button = column.children  # type: ignore[union-attr]
        self.renderer.operations.clear()

        root = self.reconciler.render(Column(Text("two"), Button("Save")))
        self.assertIs(root.handle, column)
        self.assertIs(root.handle.children[0], text)  # type: ignore[union-attr]
        self.assertIs(root.handle.children[1], button)  # type: ignore[union-attr]
        self.assertEqual(text.props["value"], "two")
        self.assertEqual([entry[0] for entry in self.renderer.operations], ["update"])

    def test_keyed_reorder_preserves_identity_and_moves(self) -> None:
        root = self.reconciler.render(Row(Text("A", key="a"), Text("B", key="b"), Text("C", key="c")))
        handles = {handle.props["value"]: handle for handle in root.handle.children}  # type: ignore[union-attr]
        self.renderer.operations.clear()

        root = self.reconciler.render(Row(Text("C", key="c"), Text("B", key="b"), Text("A", key="a")))
        current = root.handle.children  # type: ignore[union-attr]
        self.assertEqual([item.props["value"] for item in current], ["C", "B", "A"])
        self.assertIs(current[0], handles["C"])
        self.assertIs(current[1], handles["B"])
        self.assertIs(current[2], handles["A"])
        self.assertIn("move", [entry[0] for entry in self.renderer.operations])
        self.assertNotIn("destroy", [entry[0] for entry in self.renderer.operations])

    def test_duplicate_keys_fail_deterministically(self) -> None:
        with self.assertRaises(DuplicateKeyError):
            self.reconciler.render(Row(Text("A", key="same"), Text("B", key="same")))

    def test_event_slot_updates_without_a_second_connection(self) -> None:
        calls: list[str] = []
        self.reconciler.render(Button("Save", on_click=lambda: calls.append("old")))
        handle = self.reconciler.root.handle  # type: ignore[union-attr]
        handle.events["on_click"].invoke()
        self.reconciler.render(Button("Save", on_click=lambda: calls.append("new")))
        handle.events["on_click"].invoke()
        self.assertEqual(calls, ["old", "new"])
        self.assertEqual(sum(1 for op in self.renderer.operations if op[0] == "bind_event"), 1)

    def test_unmount_unbinds_and_destroys_once(self) -> None:
        self.reconciler.render(Column(Button("Save", on_click=lambda: None)))
        self.reconciler.unmount()
        self.reconciler.unmount()
        names = [operation[0] for operation in self.renderer.operations]
        self.assertEqual(names.count("unbind_event"), 1)
        self.assertEqual(names.count("destroy"), 2)

    def test_component_definition_has_stable_identity_and_renders_via_reconciler(self) -> None:
        @component
        def Greeting(name: str):
            return Text(f"Hello, {name}")

        root = self.reconciler.render(Column(Greeting(name="Ada")))
        self.assertEqual(root.handle.children[0].props["value"], "Hello, Ada")  # type: ignore[union-attr]
        self.reconciler.render(Column(Greeting(name="Grace")))
        self.assertEqual(root.handle.children[0].props["value"], "Hello, Grace")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
