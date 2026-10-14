"""Grammar preflight characterization; F5-G2–G4 own execution semantics."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.markup.compile import psx
from psx.markup.expressive_syntax import ExpressiveOperator, inspect_expressive_expression
from psx.markup.transform import transform_source


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

    def test_existing_static_lexical_pipeline_is_untouched(self):
        result = transform_source(
            "from psx import psx\ndef view():\n    return psx('<Text value={title} />')\n",
            filename="old_code.py")
        self.assertEqual(result.transformed_calls, 1)
        self.assertEqual(len(result.source_map.entries), 1)


if __name__ == "__main__":
    unittest.main()
