from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from psx import Button, Column, MarkupSyntaxError, Text, component, psx, use_state
from psx.core.reconcile import Reconciler
from psx.markup import compile_template
from psx.renderers.headless import HeadlessRenderer


class MarkupM4ATests(unittest.TestCase):
    def test_markup_and_python_builders_create_equivalent_vnodes(self) -> None:
        calls: list[str] = []

        def increment() -> None:
            calls.append("increment")

        markup = psx(
            """
            <Column spacing={gap}>
                <Text>Count: {count}</Text>
                <Button on_click={increment}>+1</Button>
            </Column>
            """,
            scope={"gap": 12, "count": 3, "increment": increment},
        )
        python = Column(Text("Count: 3"), Button("+1", on_click=increment), spacing=12)
        self.assertEqual(markup, python)

    def test_fragment_and_custom_component_share_the_vnode_pipeline(self) -> None:
        @component
        def UserCard(user: dict[str, str]):
            return Text(user["name"])

        tree = psx(
            "<><UserCard user={user} /><Text>Done</Text></>",
            scope={"UserCard": UserCard, "user": {"name": "Ada"}},
        )
        self.assertEqual(tree.kind.value, "fragment")
        self.assertEqual(tree.children[0].type, UserCard)
        self.assertEqual(tree.children[0].props["user"], {"name": "Ada"})

    def test_dotted_references_are_mapping_only(self) -> None:
        tree = psx("<Text>{user.name}</Text>", scope={"user": {"name": "Ada"}})
        self.assertEqual(tree.props["value"], "Ada")
        with self.assertRaises(MarkupSyntaxError) as error:
            psx("<Text>{user.name}</Text>", scope={"user": object()})
        self.assertIn("mapping values", str(error.exception))

    def test_templates_are_cached_without_capturing_scope_values(self) -> None:
        first = compile_template("<Text>{count}</Text>")
        second = compile_template("<Text>{count}</Text>")
        self.assertIs(first, second)
        self.assertEqual(first.render({"count": 1}).props["value"], "1")
        self.assertEqual(second.render({"count": 2}).props["value"], "2")

    def test_untrusted_expression_syntax_is_rejected_without_evaluation(self) -> None:
        with self.assertRaises(MarkupSyntaxError) as error:
            psx("<Text>{__import__('os')}</Text>", scope={})
        self.assertIn("References must be identifiers", str(error.exception))

    def test_missing_scope_and_malformed_markup_have_source_diagnostics(self) -> None:
        with self.assertRaises(MarkupSyntaxError) as missing:
            psx("<Text>{count}</Text>")
        self.assertIn("scope", str(missing.exception))
        with self.assertRaises(MarkupSyntaxError) as malformed:
            psx("<Column>\n<Text>Hello</Column>", filename="counter.psx")
        self.assertIn("counter.psx:2", str(malformed.exception))
        self.assertIn("Expected closing tag </Text>", str(malformed.exception))

    def test_static_spacing_is_converted_by_the_column_schema(self) -> None:
        tree = psx('<Column spacing="16"><Text>Hello</Text></Column>')
        self.assertEqual(tree.props["spacing"], 16)

    def test_braced_numeric_literals_are_safe_static_attribute_values(self) -> None:
        tree = psx('<Column padding={50} spacing={12}><Text>Ready</Text></Column>')
        self.assertEqual(tree.props["padding"], 50)
        self.assertEqual(tree.props["spacing"], 12)

    def test_markup_component_uses_the_same_state_event_and_reconciliation_pipeline(self) -> None:
        renderer = HeadlessRenderer()
        reconciler = Reconciler(renderer)

        @component
        def Counter():
            count, set_count = use_state(0)

            def increment() -> None:
                set_count(lambda current: current + 1)

            return psx(
                """
                <Column spacing={spacing}>
                    <Text>Count: {count}</Text>
                    <Button on_click={increment}>+1</Button>
                </Column>
                """,
                scope={"spacing": 8, "count": count, "increment": increment},
            )

        root = reconciler.render(Counter())
        column = root.children[0].handle
        label = column.children[0]
        button = column.children[1]
        button.events["on_click"].invoke()
        renderer.flush()
        self.assertIs(root.children[0].handle, column)
        self.assertIs(column.children[0], label)
        self.assertIs(column.children[1], button)
        self.assertEqual(label.props["value"], "Count: 1")


if __name__ == "__main__":
    unittest.main()
