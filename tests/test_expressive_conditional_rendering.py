"""Executable F5 conditional behavior through M4B + Headless reconciliation."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.core.reconcile import Reconciler
from psx.markup import psx
from psx.markup.transform import transform_source
from psx.renderers.headless import HeadlessRenderer


def _view(source: str):
    transformed = transform_source(source, filename="conditional_view.py")
    namespace = {"__name__": "conditional_view_fixture"}
    exec(compile(transformed.source, "conditional_view.py", "exec"), namespace)
    return namespace, transformed


class ConditionalMarkupTests(unittest.TestCase):
    def test_static_markup_with_quoted_question_mark_uses_legacy_m4b(self):
        namespace, result = _view("""
from psx import psx
def view():
    return psx('<Text value="Why?" />')
""")
        self.assertEqual(result.transformed_calls, 1)
        self.assertIn("_psx_template_0.render_lexical", result.source)
        self.assertEqual(namespace["view"]().props["value"], "Why?")

    def test_quoted_ampersands_and_plain_text_do_not_activate_expressions(self):
        namespace, result = _view("""
from psx import psx
def view():
    return psx('<Text value="A && B" />')
""")
        self.assertEqual(result.transformed_calls, 1)
        self.assertIn("_psx_template_0.render_lexical", result.source)
        self.assertEqual(namespace["view"]().props["value"], "A && B")

    def test_plain_numeric_text_interpolation_preserves_zero(self):
        namespace, _ = _view("""
from psx import psx
def view(enabled, count):
    return psx('<Flex><Text>{count}</Text>{enabled && <Text value="Extra" />}</Flex>')
""")
        node = namespace["view"](False, 0)
        self.assertEqual(node.children[0].props["value"], "0")
        self.assertEqual(len(node.children), 1)

    def test_source_map_records_real_conditional_reference_positions(self):
        markup = '<Flex>{ready && <Text value={label} />}</Flex>'
        source = "from psx import psx\ndef view(ready, label):\n    return psx(" + repr(markup) + ")\n"
        result = transform_source(source, filename="source_map.py")
        positions = result.source_map.entries[0].markup_references
        self.assertIn((1, markup.index("ready") + 1), positions)
        self.assertIn((1, markup.index("label") + 1), positions)

    def test_conditional_false_true_and_zero_emit_no_child(self):
        namespace, result = _view("""
from psx import psx
def view(visible):
    return psx('<Flex>{visible && <Text value="Visible" />}</Flex>')
""")
        self.assertEqual(result.transformed_calls, 1)
        view = namespace["view"]
        self.assertEqual(len(view(False).children), 0)
        self.assertEqual(len(view(0).children), 0)
        self.assertEqual(len(view("").children), 0)
        self.assertEqual(len(view(True).children), 1)
        self.assertEqual(view(True).children[0].type, "Text")

    def test_nested_ternary_is_lazy_and_right_associative(self):
        namespace, _ = _view("""
from psx import psx
def view(first, second):
    return psx('<Flex>{first ? <Text value="A" /> : second ? <Text value="B" /> : <Text value="C" />}</Flex>')
""")
        view = namespace["view"]
        self.assertEqual(view(True, False).children[0].props["value"], "A")
        self.assertEqual(view(False, True).children[0].props["value"], "B")
        self.assertEqual(view(False, False).children[0].props["value"], "C")

    def test_boolean_comparison_python_semantics(self):
        namespace, _ = _view("""
from psx import psx
def view(status):
    return psx('<Flex>{status == "ready" && <Text value="OK" />}</Flex>')
""")
        self.assertEqual(len(namespace["view"]("pending").children), 0)
        self.assertEqual(len(namespace["view"]("ready").children), 1)

    def test_inactive_branch_never_invokes_condition_function(self):
        namespace, _ = _view("""
from psx import psx
calls = []
def dangerous():
    calls.append("called")
    return True
def view(enabled):
    return psx('<Flex>{enabled && dangerous() && <Text value="OK" />}</Flex>')
""")
        namespace["view"](False)
        self.assertEqual(namespace["calls"], [])
        namespace["view"](True)
        self.assertEqual(namespace["calls"], ["called"])

    def test_missing_lexical_name_has_markup_diagnostics(self):
        namespace, _ = _view("""
from psx import psx
def view():
    return psx('<Flex>{unknown && <Text value="X" />}</Flex>')
""")
        with self.assertRaises(MarkupSyntaxError) as error:
            namespace["view"]()
        self.assertIn("Unknown lexical identifier 'unknown'", str(error.exception))
        self.assertIn("conditional_view.py", str(error.exception))

    def test_not_equal_python_comparison_in_conditional(self):
        namespace, _ = _view("""
from psx import psx
def view(status):
    return psx('<Flex>{status != "ready" && <Text value="Waiting" />}</Flex>')
""")
        self.assertEqual(len(namespace["view"]("ready").children), 0)
        self.assertEqual(namespace["view"]("pending").children[0].props["value"], "Waiting")

    def test_nested_widget_inside_text_only_content_is_rejected(self):
        namespace, _ = _view("""
from psx import psx
def view(visible):
    return psx('<Flex>{visible && <Text><Button label="Invalid" /></Text>}</Flex>')
""")
        with self.assertRaisesRegex(MarkupSyntaxError, "textual content"):
            namespace["view"](True)

    def test_invalid_arrow_outside_approved_grammar_fails_closed(self):
        sources = (
            '<Flex>{visible && <Button on_click={(item, index) => save(item)} />}</Flex>',
        )
        for markup in sources:
            with self.subTest(markup=markup):
                module = "from psx import psx\ndef view(visible, items=None):\n    return psx(" + repr(markup) + ")\n"
                with self.assertRaises(MarkupSyntaxError):
                    transform_source(module, filename="future_syntax.py")

    def test_explicit_scope_m4a_remains_unchanged(self):
        with self.assertRaises(MarkupSyntaxError):
            psx('<Flex>{enabled && <Text value="X" />}</Flex>',
                scope={"enabled": True})

    def test_conditionally_rendered_child_preserves_native_parent(self):
        namespace, _ = _view("""
from psx import psx, component, use_state
@component
def View():
    active, set_active = use_state(False)
    def toggle():
        set_active(lambda value: not value)
    return psx('<Flex><Button label="Toggle" on_click={toggle} />{active && <Text value="Shown" />}</Flex>')
""")
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
        renderer = HeadlessRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(640, True), AvailableSize(480, True)
            ),
            engine=PythonLayoutEngine(),
            measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
        )
        root = Reconciler(renderer).render(namespace["View"]())
        flex = root.children[0].handle
        self.assertEqual(len(flex.children), 1)
        flex.children[0].events["on_click"].invoke()
        renderer.flush()
        self.assertIs(root.children[0].handle, flex)
        self.assertEqual(len(flex.children), 2)
        flex.children[0].events["on_click"].invoke()
        renderer.flush()
        self.assertEqual(len(flex.children), 1)


if __name__ == "__main__":
    unittest.main()
