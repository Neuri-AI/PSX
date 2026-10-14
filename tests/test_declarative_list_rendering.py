"""G3 executable keyed list semantics via static M4B transformation."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.core.reconcile import Reconciler
from psx.markup import psx
from psx.markup.transform import transform_source
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints


def transformed_view(markup: str):
    source = (
        "from psx import psx\n"
        "def view(items):\n"
        "    return psx(" + repr(markup) + ")\n"
    )
    result = transform_source(source, filename="keyed_list.py")
    namespace = {"__name__": "keyed_list_fixture"}
    exec(compile(result.source, "keyed_list.py", "exec"), namespace)
    return namespace["view"], result


class DeclarativeListsTests(unittest.TestCase):
    MARKUP = '<Flex>{items.map((item) => <Text key={item.id}>{item.label}</Text>)}</Flex>'

    def test_map_is_static_compiler_syntax_not_python_list_method(self):
        view, result = transformed_view(self.MARKUP)
        self.assertEqual(result.transformed_calls, 1)
        self.assertNotIn(".map(", result.source)
        self.assertEqual(tuple(child.props["value"] for child in
                               view([{"id": "a", "label": "A"},
                                     {"id": "b", "label": "B"}]).children), ("A", "B"))

    def test_empty_insert_remove_reorder_preserves_order_and_keys(self):
        view, _ = transformed_view(self.MARKUP)
        self.assertEqual(view([]).children, ())
        first = view([{"id": "a", "label": "A"}, {"id": "b", "label": "B"}])
        second = view([{"id": "b", "label": "B"}, {"id": "a", "label": "A"},
                       {"id": "c", "label": "C"}])
        self.assertEqual(tuple(x.key for x in first.children), ("a", "b"))
        self.assertEqual(tuple(x.key for x in second.children), ("b", "a", "c"))

    def test_duplicate_key_missing_key_and_invalid_iterable_fail_closed(self):
        view, _ = transformed_view(self.MARKUP)
        cases = (
            ([{"id": "same", "label": "A"}, {"id": "same", "label": "B"}], "Duplicate"),
            ([{"id": None, "label": "A"}], "stable"),
            (42, "iterable"),
        )
        for value, error in cases:
            with self.subTest(value=value):
                with self.assertRaisesRegex(MarkupSyntaxError, error):
                    view(value)

    def test_lexical_item_does_not_capture_final_loop_value(self):
        view, _ = transformed_view(
            '<Flex>{items.map((item) => <Text key={item.id} value={item.label} />)}</Flex>')
        result = view([{"id": 1, "label": "First"}, {"id": 2, "label": "Last"}])
        self.assertEqual(tuple(child.props["value"] for child in result.children),
                         ("First", "Last"))

    def test_nested_maps_keep_independent_item_scopes(self):
        view, _ = transformed_view(
            '<Flex>{items.map((item) => <Flex key={item.id}>'
            '{item.children.map((child) => <Text key={child.id} value={child.name} />)}'
            '</Flex>)}</Flex>'
        )
        data = [
            {"id": "p1", "children": [{"id": "a", "name": "Alpha"}]},
            {"id": "p2", "children": [{"id": "b", "name": "Beta"}]},
        ]
        output = view(data)
        self.assertEqual(output.children[0].children[0].props["value"], "Alpha")
        self.assertEqual(output.children[1].children[0].props["value"], "Beta")

    def test_map_works_inside_conditional_branch(self):
        source = '<Flex>{items && items.map((item) => <Text key={item.id} value={item.label} />)}</Flex>'
        view, _ = transformed_view(source)
        self.assertEqual(view([]).children, ())
        self.assertEqual(tuple(x.key for x in view([{"id": 1, "label": "One"}]).children),
                         (1,))

    def test_static_grammar_rejects_missing_key_or_two_parameters(self):
        for markup in (
            '<Flex>{items.map((item) => <Text value={item.label} />)}</Flex>',
            '<Flex>{items.map((item, index) => <Text key={item.id} />)}</Flex>',
        ):
            with self.subTest(markup=markup):
                with self.assertRaises(MarkupSyntaxError):
                    transformed_view(markup)

    def test_explicit_scope_m4a_remains_restricted(self):
        with self.assertRaises(MarkupSyntaxError):
            psx(self.MARKUP, scope={"items": []})

    def test_native_reconciliation_keeps_keyed_widget_identity(self):
        view, _ = transformed_view(self.MARKUP)
        renderer = HeadlessRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(640, True), AvailableSize(480, True)),
            engine=PythonLayoutEngine(),
            measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
        )
        reconciler = Reconciler(renderer)
        items = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
        root = reconciler.render(view(items))
        original = {child.node.key: child.handle for child in root.children}
        root = reconciler.render(view(list(reversed(items))))
        self.assertEqual(tuple(child.node.key for child in root.children), ("b", "a"))
        self.assertIs(root.children[0].handle, original["b"])
        self.assertIs(root.children[1].handle, original["a"])
        reconciler.unmount()


if __name__ == "__main__":
    unittest.main()
