from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import HookOrderError, Text, ThreadViolationError, component, use_effect, use_ref, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


class HooksAndSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = HeadlessRenderer()
        self.reconciler = Reconciler(self.renderer)

    def test_batched_functional_state_updates_commit_once(self) -> None:
        captured: dict[str, object] = {}

        @component
        def Counter():
            count, set_count = use_state(0)
            captured["set"] = set_count
            return Text(str(count))

        root = self.reconciler.render(Counter())
        label = root.children[0].handle
        self.renderer.operations.clear()
        setter = captured["set"]
        setter(lambda current: current + 1)
        setter(lambda current: current + 1)
        setter(lambda current: current + 1)
        self.assertEqual(label.props["value"], "0")
        self.renderer.flush()
        self.assertEqual(label.props["value"], "3")
        self.assertEqual([op[0] for op in self.renderer.operations], ["update"])

    def test_effect_cleanup_precedes_the_next_effect(self) -> None:
        captured: dict[str, object] = {}
        log: list[str] = []

        @component
        def Example():
            value, set_value = use_state(0)
            captured["set"] = set_value

            def effect():
                log.append(f"setup:{value}")
                return lambda: log.append(f"cleanup:{value}")

            use_effect(effect, [value])
            return Text(str(value))

        self.reconciler.render(Example())
        self.assertEqual(log, ["setup:0"])
        captured["set"](1)
        self.renderer.flush()
        self.assertEqual(log, ["setup:0", "cleanup:0", "setup:1"])
        self.reconciler.unmount()
        self.assertEqual(log, ["setup:0", "cleanup:0", "setup:1", "cleanup:1"])

    def test_ref_is_populated_after_commit_and_cleared_before_destroy(self) -> None:
        captured: dict[str, object] = {}

        @component
        def Example():
            ref = use_ref()
            captured["ref"] = ref
            return Text("ready", ref=ref)

        self.reconciler.render(Example())
        ref = captured["ref"]
        self.assertIsNotNone(ref.current)
        self.reconciler.unmount()
        self.assertIsNone(ref.current)

    def test_hook_order_mismatch_is_a_development_error(self) -> None:
        @component
        def Conditional(enabled: bool):
            if enabled:
                use_state(0)
            return Text("ok")

        self.reconciler.render(Conditional(enabled=True))
        with self.assertRaises(HookOrderError):
            self.reconciler.render(Conditional(enabled=False))

    def test_worker_setter_defers_native_mutation_to_the_renderer_queue(self) -> None:
        captured: dict[str, object] = {}

        @component
        def Counter():
            count, set_count = use_state(0)
            captured["set"] = set_count
            return Text(str(count))

        root = self.reconciler.render(Counter())
        label = root.children[0].handle
        self.renderer.operations.clear()
        worker = threading.Thread(target=lambda: captured["set"](1))
        worker.start()
        worker.join()
        self.assertEqual(label.props["value"], "0")
        self.assertEqual(self.renderer.operations, [])
        self.renderer.flush()
        self.assertEqual(label.props["value"], "1")

    def test_state_updates_during_render_are_rejected_and_unmounted_setter_is_inert(self) -> None:
        captured: dict[str, object] = {}

        @component
        def Counter():
            value, set_value = use_state(0)
            captured["set"] = set_value
            return Text(str(value))

        self.reconciler.render(Counter())
        self.reconciler.unmount()
        captured["set"](1)
        self.renderer.flush()
        self.assertIsNone(self.reconciler.root)

        @component
        def Invalid():
            _, set_value = use_state(0)
            set_value(1)
            return Text("never")

        with self.assertRaises(ThreadViolationError):
            self.reconciler.render(Invalid())


def test_state_driven_css_paint_burst_skips_layout_but_reflows_dimensions():
    from psx import psx
    from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(320, True), AvailableSize(180, True)),
        measure_intrinsic=lambda _: IntrinsicSizes(30, 30, 12, 12, 30, 12),
    )
    reconciler = Reconciler(renderer)
    calls = []
    original_commit = renderer.commit_layout

    def counted(root):
        calls.append(root)
        return original_commit(root)

    renderer.commit_layout = counted
    state = {}

    @component
    def Panel():
        color, set_color = use_state("#123456")
        width, set_width = use_state(120)
        state["color"] = set_color
        state["width"] = set_width
        return psx(
            f'<div style="width: {width}px; color: {color}">'
            '<button key="save" label="Save"/></div>'
        )

    try:
        root = reconciler.render(Panel())
        native_handle = root.children[0].children[0].handle
        assert len(calls) == 1
        for index in range(100):
            state["color"]("#654321" if index % 2 else "#123456")
        renderer.flush()
        assert len(calls) == 1
        assert reconciler.root.children[0].children[0].handle is native_handle
        state["width"](150)
        renderer.flush()
        assert len(calls) == 2
    finally:
        reconciler.unmount()


if __name__ == "__main__":
    unittest.main()


def test_unmount_releases_queued_state_and_effect_payloads_without_ui_flush():
    import gc
    import weakref
    from psx import component, Text, use_state, use_effect
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer

    class Payload:
        pass

    renderer = HeadlessRenderer()
    tree = Reconciler(renderer)
    held = {}
    payload = Payload()
    reference = weakref.ref(payload)

    @component
    def Item():
        value, setter = use_state(0)
        held["setter"] = setter
        use_effect(lambda: None, (value,))
        return Text(str(value))

    tree.render(Item())
    # Queue an update whose renderer callback is not dispatched yet.
    held["setter"](1)
    assert tree.scheduler._dirty
    # Explicitly queue an effect closure that captures an otherwise unowned object.
    tree.scheduler.queue_effect(tree.root, 99, lambda captured=payload: captured)
    del payload
    gc.collect()
    assert reference() is not None
    tree.unmount()
    gc.collect()
    assert tree.scheduler._dirty == {}
    assert tree.scheduler._effects == {}
    assert reference() is None
    # A stale scheduled UI callback must not re-render disposed components.
    renderer.flush()
    assert tree.root is None
    # The same reconciler remains reusable after teardown.
    tree.render(Item())
    held["setter"](2)
    renderer.flush()
    assert tree.root.children[0].handle.props["value"] == "2"
    tree.unmount()
