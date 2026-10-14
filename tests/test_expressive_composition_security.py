"""Cross-feature expressive composition and fail-closed security regressions."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.core.reconcile import Reconciler
from psx.markup import psx
from psx.markup.transform import transform_source
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints


def compiled(markup):
    source = ("from psx import psx\n"
              "def view(items, enabled, handler):\n"
              "    return psx(" + repr(markup) + ")\n")
    transformed = transform_source(source, filename="composition_fixture.py")
    namespace = {"__name__": "composition_fixture"}
    exec(compile(transformed.source, "composition_fixture.py", "exec"), namespace)
    return namespace["view"], transformed


def renderer():
    return HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )


class ExpressiveCompositionTests(unittest.TestCase):
    MARKUP = (
        '<Flex>{enabled ? items.map((item) => '
        '<Button key={item.id} label={item.label} '
        'on_click={() => handler(item.id)} />) : '
        '<Text value="Inactive" />}</Flex>'
    )

    def test_ternary_map_arrow_and_native_reorder_preserve_keys(self):
        calls = []
        view, transformed = compiled(self.MARKUP)
        self.assertEqual(transformed.transformed_calls, 1)
        items = [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}]
        reconciler = Reconciler(renderer())
        first = reconciler.render(view(items, True, calls.append))
        handles = {child.node.key: child.handle for child in first.children}
        first.children[1].handle.events["on_click"].invoke()
        self.assertEqual(calls, ["b"])
        reordered = reconciler.render(view(list(reversed(items)), True, calls.append))
        self.assertEqual(tuple(x.node.key for x in reordered.children), ("b", "a"))
        self.assertIs(reordered.children[0].handle, handles["b"])
        self.assertIs(reordered.children[1].handle, handles["a"])
        reconciler.unmount()

    def test_inactive_branch_does_not_invoke_map_or_event(self):
        calls = []
        view, _ = compiled(self.MARKUP)
        output = view(None, False, calls.append)
        self.assertEqual(output.children[0].props["value"], "Inactive")
        self.assertEqual(calls, [])

    def test_invalid_list_does_not_mutate_mounted_root(self):
        view, _ = compiled(self.MARKUP)
        reconciler = Reconciler(renderer())
        old = reconciler.render(view([{"id": "stable", "label": "OK"}], True, lambda x: x))
        handle = old.children[0].handle
        with self.assertRaisesRegex(MarkupSyntaxError, "Duplicate"):
            reconciler.render(view([{"id": "x", "label": "X"},
                                    {"id": "x", "label": "Y"}], True, lambda x: x))
        self.assertIs(reconciler.root, old)
        self.assertIs(reconciler.root.children[0].handle, handle)
        reconciler.unmount()

    def test_dunder_introspection_is_rejected_with_source_diagnostic(self):
        view, _ = compiled('<Flex>{enabled && <Text value={items.__class__} />}</Flex>')
        with self.assertRaisesRegex(MarkupSyntaxError, "Private lexical attribute") as error:
            view([], True, lambda x: x)
        self.assertIn("composition_fixture.py", str(error.exception))

    def test_mapping_private_fields_are_inaccessible_too(self):
        view, _ = compiled('<Flex>{enabled && <Text value={items._secret} />}</Flex>')
        with self.assertRaisesRegex(MarkupSyntaxError, "Private lexical attribute"):
            view({"_secret": "private"}, True, lambda x: x)

    def test_m4a_never_executes_expressive_callbacks(self):
        with self.assertRaises(MarkupSyntaxError):
            psx(self.MARKUP, scope={"enabled": True, "items": [], "handler": lambda x: x})

    def test_unsupported_strict_equality_rejected(self):
        with self.assertRaises(MarkupSyntaxError):
            compiled('<Flex>{enabled === True ? <Text value="Yes" /> : <Text value="No" />}</Flex>')


if __name__ == "__main__":
    unittest.main()
