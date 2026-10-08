from __future__ import annotations

import sys
import threading
import unittest

sys.path.insert(0, "src")

from psx import Column, HookOrderError, Text, ThreadViolationError, component, use_effect, use_ref, use_state
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


if __name__ == "__main__":
    unittest.main()
