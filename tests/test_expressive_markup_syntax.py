"""Grammar preflight characterization; F5-G2–G4 own execution semantics."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.markup.compile import psx
from psx.markup.expressive_syntax import ExpressiveOperator, inspect_expressive_expression
from psx.markup.transform import transform_source
from psx.markup.expressive_ast import Arrow, Call, Compare, ConditionalAnd, Element, Fragment, Map, Member, Ternary, parse_expressive_expression


class ExpressiveGrammarTests(unittest.TestCase):
    def operators(self, source):
        return tuple(token.operator for token in inspect_expressive_expression(source).tokens)

    def test_conditional_and_equality(self):
        self.assertEqual(
            self.operators("status == 'ready' && <Text />"),
            (ExpressiveOperator.EQUAL, ExpressiveOperator.AND),
        )

    def test_nested_ternary_tokens_and_preserve_order(self):
        self.assertEqual(
            self.operators("first ? <A /> : second ? <B /> : <C />"),
            (ExpressiveOperator.TERNARY, ExpressiveOperator.BRANCH,
             ExpressiveOperator.TERNARY, ExpressiveOperator.BRANCH),
        )

    def test_map_and_arrow(self):
        self.assertEqual(
            self.operators("items.map((item) => <Text key={item.id} />)"),
            (ExpressiveOperator.MAP, ExpressiveOperator.ARROW),
        )

    def test_empty_arrow(self):
        self.assertEqual(
            self.operators("() => save()"), (ExpressiveOperator.ARROW,),
        )

    def test_not_equal_python_semantics_token(self):
        self.assertEqual(self.operators("a != b"), (ExpressiveOperator.NOT_EQUAL,))

    def test_literals_do_not_contribute_operators(self):
        self.assertEqual(
            self.operators("'&& === => .map(' && <Text />"),
            (ExpressiveOperator.AND,),
        )

    def test_precise_multiline_source_location(self):
        inspection = inspect_expressive_expression(
            "ready\n  && <Text />", filename="view.psx", line=7, column=4)
        self.assertEqual(
            (inspection.tokens[0].line, inspection.tokens[0].column), (8, 3))

    def test_strict_comparison_is_rejected_with_location(self):
        for source in ("a === b", "a !== b"):
            with self.subTest(source=source):
                with self.assertRaises(MarkupSyntaxError) as caught:
                    inspect_expressive_expression(source, filename="view.psx")
                self.assertEqual(caught.exception.filename, "view.psx")
                self.assertEqual(caught.exception.column, 3)

    def test_invalid_delimiters_and_quotes(self):
        for source in ("items.map((item) => <Text />", "value)", "'value"):
            with self.subTest(source=source):
                with self.assertRaises(MarkupSyntaxError):
                    inspect_expressive_expression(source)

    def test_template_directive_rejection(self):
        with self.assertRaisesRegex(MarkupSyntaxError, "control directives"):
            inspect_expressive_expression("{#if ready}")

    def test_no_untrusted_m4a_execution_escape(self):
        with self.assertRaises(MarkupSyntaxError):
            psx("<Text>{ready && <Button />}</Text>", scope={"ready": True})
        with self.assertRaises(MarkupSyntaxError):
            psx("<Text value={items.map((item) => item)} />",
                scope={"items": [1, 2]})

    def test_braced_literal_number_is_rejected_in_markup_attributes(self):
        for declaration in ('<Flex gap={12} />', '<Flex gap={0.5} />'):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(
                    MarkupSyntaxError, "Braces are reserved for references"
                ):
                    psx(declaration, filename="literal.psx")

    def test_quoted_numeric_literal_is_coerced_by_existing_schema(self):
        tree = psx('<Flex gap="12" padding="50"><Text value="Ready" /></Flex>')
        self.assertEqual(tree.props["gap"], 12)
        self.assertEqual(tree.props["padding"], 50)

    def test_defined_reference_can_resolve_numeric_attribute(self):
        tree = psx('<Flex gap={spacing} />', scope={"spacing": 12})
        self.assertEqual(tree.props["gap"], 12)

    def test_undefined_reference_has_precise_source_diagnostic(self):
        with self.assertRaises(MarkupSyntaxError) as error:
            psx('<Flex gap={missing_spacing} />', filename="unknown.psx")
        self.assertEqual(error.exception.filename, "unknown.psx")
        self.assertIn("Unknown identifier 'missing_spacing'", str(error.exception))

    def test_braces_do_not_evaluate_undefined_lexical_identifier(self):
        source = (
            "from psx import psx\n"
            "def view():\n"
            "    return psx('<Flex gap={unknown_local} />')\n"
        )
        result = transform_source(source, filename="unknown_local.py")
        self.assertEqual(result.transformed_calls, 1)
        self.assertIn("unknown_local", result.source)


    def test_parsed_comparison_precedes_conditional_and(self):
        tree = parse_expressive_expression("ready == True && <Text />")
        self.assertIsInstance(tree, ConditionalAnd)
        self.assertIsInstance(tree.left, Compare)
        self.assertIsInstance(tree.right, Element)

    def test_parsed_nested_ternary_is_right_associative(self):
        tree = parse_expressive_expression("first ? <A /> : second ? <B /> : <C />")
        self.assertIsInstance(tree, Ternary)
        self.assertIsInstance(tree.no, Ternary)

    def test_parsed_nested_jsx_and_fragment(self):
        tree = parse_expressive_expression("<Flex><><Text>{user.name}</Text></><Button /></Flex>")
        self.assertIsInstance(tree, Element)
        self.assertIsInstance(tree.children[0], Fragment)
        self.assertIsInstance(tree.children[0].children[0].children[0], Member)

    def test_parsed_map_arrow_item_scope_structure(self):
        tree = parse_expressive_expression("items.map((item) => <Text key={item.id}>{item.name}</Text>)")
        self.assertIsInstance(tree, Map)
        self.assertEqual(tree.callback.parameters, ("item",))
        self.assertIsInstance(tree.callback.body, Element)

    def test_parsed_map_arrow_item_and_index(self):
        tree = parse_expressive_expression(
            "items.map((item, index) => <Text key={index}>{item}</Text>)"
        )
        self.assertIsInstance(tree, Map)
        self.assertEqual(tree.callback.parameters, ("item", "index"))

    def test_duplicate_map_parameters_are_rejected(self):
        with self.assertRaises(MarkupSyntaxError):
            parse_expressive_expression(
                "items.map((item, item) => <Text key={item.id} />)"
            )

    def test_parsed_zero_argument_arrow(self):
        tree = parse_expressive_expression("() => save()")
        self.assertIsInstance(tree, Arrow)
        self.assertEqual(tree.parameters, ())
        self.assertIsInstance(tree.body, Call)

    def test_parsed_arrow_attribute(self):
        tree = parse_expressive_expression("<Button on_click={(value) => save(value)} />")
        self.assertIsInstance(tree.attributes[0][1], Arrow)

    def test_parsed_invalid_grammar_is_rejected(self):
        for source in ("items.map((item, idx, extra) => <Text />)", "items.map(save)",
                       "async () => save()", "ready === True", "ready !== True",
                       "<Flex><Text /></Button>", "items.map((item) => <Text />"):
            with self.subTest(source=source):
                with self.assertRaises(MarkupSyntaxError):
                    parse_expressive_expression(source)

    def test_parsed_jsx_rejects_braced_literals_and_unkeyed_map(self):
        for source in ('<Flex gap={12} />', '<Text value={"static"} />',
                       'items.map((item) => <Text />)'):
            with self.subTest(source=source):
                with self.assertRaises(MarkupSyntaxError):
                    parse_expressive_expression(source)

    def test_parsed_keyed_map_supports_nested_ternary_body(self):
        tree = parse_expressive_expression(
            "items.map((item) => item.ready ? <Text key={item.id} /> : <Button key={item.id} />)"
        )
        self.assertIsInstance(tree, Map)
        self.assertIsInstance(tree.callback.body, Ternary)

    def test_parsed_escaped_string_does_not_execute_python(self):
        tree = parse_expressive_expression('name == "hello\\nworld"')
        self.assertIsInstance(tree, Compare)
        self.assertEqual(tree.right.value, "hello\nworld")

    def test_parsed_source_positions(self):
        node = parse_expressive_expression("ready ?\n  <Text /> : <Button />",
                                          filename="screen.psx", line=12, column=5)
        self.assertEqual((node.yes.location.line, node.yes.location.column), (13, 3))

    def test_parser_does_not_evaluate_calls_or_escape_m4a(self):
        tree = parse_expressive_expression("dangerous() && <Text />")
        self.assertIsInstance(tree.left, Call)
        with self.assertRaises(MarkupSyntaxError):
            psx("<Flex>{dangerous() && <Text />}</Flex>", scope={})

    def test_existing_static_lexical_pipeline_is_untouched(self):
        result = transform_source(
            "from psx import psx\ndef view():\n    return psx('<Text value={title} />')\n",
            filename="old_code.py")
        self.assertEqual(result.transformed_calls, 1)
        self.assertEqual(len(result.source_map.entries), 1)


if __name__ == "__main__":
    unittest.main()
