"""M4B arrow callback contracts: lexical binding, deferred events, and keyed list scopes."""

import unittest

from psx.core.errors import MarkupSyntaxError
from psx.core.reconcile import Reconciler
from psx.markup import psx
from psx.markup.transform import transform_source
from psx.renderers.headless import HeadlessRenderer


def compiled(markup):
    source = ("from psx import psx\n"
              "def view(handler, items=None):\n"
              "    return psx(" + repr(markup) + ")\n")
    result = transform_source(source, filename="arrow_callbacks.py")
    namespace = {"__name__": "arrow_callback_fixture"}
    exec(compile(result.source, "arrow_callbacks.py", "exec"), namespace)
    return namespace["view"], result


class ArrowCallbacksTests(unittest.TestCase):
    def test_zero_arg_callback_is_deferred_and_captures_lexical_handler(self):
        calls = []
        view, result = compiled('<Button label="Save" on_click={() => handler()} />')
        self.assertEqual(result.transformed_calls, 1)
        node = view(lambda: calls.append("invoked"))
        self.assertEqual(calls, [])
        self.assertTrue(callable(node.props["on_click"]))
        node.props["on_click"]()
        self.assertEqual(calls, ["invoked"])

    def test_one_arg_callback_forwards_argument_only_on_invocation(self):
        calls = []
        view, _ = compiled('<Button label="Save" on_click={(value) => handler(value)} />')
        callback = view(calls.append).props["on_click"]
        self.assertEqual(calls, [])
        callback("payload")
        self.assertEqual(calls, ["payload"])

    def test_keyed_mapped_callbacks_capture_each_item(self):
        calls = []
        view, _ = compiled(
            '<Flex>{items.map((item) => '
            '<Button key={item.id} label={item.label} '
            'on_click={() => handler(item.id)} />)}</Flex>')
        node = view(calls.append, [{"id": "a", "label": "A"},
                                   {"id": "b", "label": "B"}])
        self.assertEqual(calls, [])
        node.children[1].props["on_click"]()
        node.children[0].props["on_click"]()
        self.assertEqual(calls, ["b", "a"])

    def test_headless_event_dispatch_and_rebind(self):
        calls = []
        view, _ = compiled('<Flex><Button label="Save" on_click={() => handler()} /></Flex>')
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
        renderer = HeadlessRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(640, True), AvailableSize(480, True)),
            engine=PythonLayoutEngine(),
            measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
        )
        reconciler = Reconciler(renderer)
        mounted = reconciler.render(view(lambda: calls.append("old")))
        mounted.children[0].handle.events["on_click"].invoke()
        reconciler.render(view(lambda: calls.append("new")))
        mounted.children[0].handle.events["on_click"].invoke()
        self.assertEqual(calls, ["old", "new"])
        reconciler.unmount()

    def test_unmount_disposes_arrow_event_slot(self):
        calls = []
        view, _ = compiled('<Flex><Button label="Save" on_click={() => handler()} /></Flex>')
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
        renderer = HeadlessRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(640, True), AvailableSize(480, True)),
            engine=PythonLayoutEngine(),
            measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
        )
        reconciler = Reconciler(renderer)
        mounted = reconciler.render(view(lambda: calls.append("called")))
        slot = mounted.children[0].handle.events["on_click"]
        slot.invoke()
        reconciler.unmount()
        self.assertIsNone(slot.invoke())
        self.assertEqual(calls, ["called"])

    def test_unsupported_disabled_prop_fails_closed_without_running_callback(self):
        calls = []
        view, _ = compiled(
            '<Button label="Save" disabled="true" on_click={() => handler()} />')
        from psx.core.errors import RendererCapabilityError
        with self.assertRaisesRegex(RendererCapabilityError, "Unsupported Button props"):
            view(lambda: calls.append("clicked"))
        self.assertEqual(calls, [])

    def test_two_arg_arrow_captures_both_callback_arguments(self):
        calls = []
        view, _ = compiled('<Button on_click={(a, b) => handler(a, b)} />')
        callback = view(lambda a, b: calls.append((a, b))).props["on_click"]
        callback("item", 3)
        self.assertEqual(calls, [("item", 3)])

    def test_mapped_items_receive_lexical_indices(self):
        view, _ = compiled(
            '<Flex>{items.map((item, index) => '
            '<Text key={index}>{item}</Text>)}</Flex>'
        )
        node = view(lambda: None, ["red", "green", "blue"])
        self.assertEqual([child.key for child in node.children], [0, 1, 2])
        self.assertEqual([child.props["value"] for child in node.children],
                         ["red", "green", "blue"])

    def test_mapped_callbacks_bind_item_and_index_independently(self):
        calls = []
        view, _ = compiled(
            '<Flex>{items.map((item, index) => '
            '<Button key={item.id} label={item.label} '
            'on_click={() => handler(item.id, index)} />)}</Flex>'
        )
        node = view(lambda item, index: calls.append((item, index)),
                    [{"id": "first", "label": "First"},
                     {"id": "second", "label": "Second"}])
        node.children[1].props["on_click"]()
        node.children[0].props["on_click"]()
        self.assertEqual(calls, [("second", 1), ("first", 0)])

    def test_runtime_explicit_scope_still_rejects_arrows(self):
        with self.assertRaises(MarkupSyntaxError):
            psx('<Button on_click={() => handler()} />', scope={"handler": lambda: None})


if __name__ == "__main__":
    unittest.main()
