"""Regression coverage for arithmetic inside PSX event callbacks."""
import unittest

from psx.markup.expressive_ast import Binary, Call, Arrow, parse_expressive_expression
from psx.markup.transform import transform_source


def view_from(markup):
    source = "from psx import psx\ndef view(count, set_count, name=None, set_name=None):\n    return psx(" + repr(markup) + ")\n"
    transformed = transform_source(source, filename="arithmetic_regression.py")
    namespace = {"__name__": "arithmetic_regression"}
    exec(compile(transformed.source, "arithmetic_regression.py", "exec"), namespace)
    return namespace["view"]


class ArithmeticRegressionTests(unittest.TestCase):
    def test_addition_in_deferred_callback(self):
        changes = []
        view = view_from('<button on_click={() => set_count(count + 1)}>Click Me</button>')
        node = view(4, changes.append)
        self.assertEqual(changes, [])
        node.props["on_click"]()
        self.assertEqual(changes, [5])

    def test_operator_precedence(self):
        changes = []
        node = view_from('<button on_click={() => set_count(count + 2 * 3)}>Click</button>')(4, changes.append)
        node.props["on_click"]()
        self.assertEqual(changes, [10])

    def test_input_change_uses_event_target_without_name(self):
        changes = []
        node = view_from('<input type="password" value={name} on_change={(e) => set_name(e.target.value)} />')(
            0, lambda _: None, "", changes.append
        )
        node.props["on_change"]("secret")
        self.assertEqual(changes, ["secret"])

    def test_html_input_click_callback(self):
        clicks = []
        node = view_from('<input type="text" value={name} on_click={() => set_count(count + 1)} />')(
            2, clicks.append, ""
        )
        self.assertEqual(clicks, [])
        self.assertTrue(callable(node.props["on_click"]))
        node.props["on_click"]()
        self.assertEqual(clicks, [3])

    def test_html_input_change_and_click_together(self):
        values = []
        clicks = []
        node = view_from(
            '<input type="password" value={name} on_click={() => set_count(count + 1)} '
            'on_change={(event) => set_name(event.target.value)} />'
        )(2, clicks.append, "", values.append)
        node.props["on_change"]("password")
        node.props["on_click"]()
        self.assertEqual(values, ["password"])
        self.assertEqual(clicks, [3])

    def test_arithmetic_expressions_parse_as_binary(self):
        parsed = parse_expressive_expression("count + 1")
        self.assertIsInstance(parsed, Binary)


if __name__ == "__main__":
    unittest.main()
