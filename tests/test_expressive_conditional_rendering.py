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
        renderer = HeadlessRenderer()
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
