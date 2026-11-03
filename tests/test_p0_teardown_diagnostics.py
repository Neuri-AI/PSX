"""P0 C07 regression tests: teardown attempts independent cleanup steps.

Run: python -m unittest discover -s tests -p test_p0_teardown_diagnostics.py -v
This is a renderer-free regression suite, NOT Qt/Tk/Kivy leak certification.
"""

from __future__ import annotations

import unittest

from psx.core.events import EventSlot
from psx.core.hooks import Ref, _EffectSlot
from psx.core.instance import MountedInstance
from psx.core.reconcile import Reconciler
from psx.core.vnode import create_element


class RecordingRenderer:
    def __init__(self) -> None:
        self.destroyed: list[object] = []
        self.unbound: list[object] = []
        self.invalidate_count = 0
        self.failing_unbind: object | None = None
        self.failing_destroy: object | None = None

    def destroy(self, handle: object) -> None:
        self.destroyed.append(handle)
        if handle == self.failing_destroy:
            raise RuntimeError("P0 injected native destroy failure")

    def unbind_event(self, subscription: object) -> None:
        self.unbound.append(subscription)
        if subscription == self.failing_unbind:
            raise RuntimeError("P0 injected native unbind failure")

    def invalidate_layout(self) -> None:
        self.invalidate_count += 1

    def schedule_ui(self, callback: object) -> None:
        pass


def make_tree(cleanup):
    parent = MountedInstance(node=create_element("P0Parent"), parent=None, handle="parent")
    child = MountedInstance(node=create_element("P0Child"), parent=parent, handle="child")
    parent.children.append(child)
    parent.hooks.append(
        _EffectSlot(deps=(), callback=lambda: None, cleanup=cleanup, pending=False)
    )
    return parent, child


class P0TeardownDiagnostics(unittest.TestCase):
    def test_normal_cleanup_releases_child_and_parent(self) -> None:
        called: list[str] = []
        parent, child = make_tree(lambda: called.append("cleanup"))
        renderer = RecordingRenderer()
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        reconciler.unmount()

        self.assertEqual(called, ["cleanup"])
        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertTrue(parent.disposed)
        self.assertTrue(child.disposed)
        self.assertIsNone(reconciler.root)
        self.assertEqual(renderer.invalidate_count, 1)

    def test_throwing_hook_still_releases_all_native_handles(self) -> None:
        def bad_cleanup() -> None:
            raise RuntimeError("P0 injected cleanup failure")

        parent, child = make_tree(bad_cleanup)
        renderer = RecordingRenderer()
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        with self.assertRaisesRegex(RuntimeError, "injected cleanup failure"):
            reconciler.unmount()

        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertTrue(child.disposed)
        self.assertEqual(parent.hooks, [])
        self.assertIsNone(reconciler.root)
        self.assertEqual(renderer.invalidate_count, 1)
        reconciler.unmount()
        self.assertEqual(renderer.destroyed, ["child", "parent"])

    def test_all_effect_cleanups_run_in_reverse_order_after_failure(self) -> None:
        called: list[str] = []
        parent, _ = make_tree(lambda: called.append("first"))

        def last_cleanup() -> None:
            called.append("last")
            raise ValueError("last cleanup failed")

        parent.hooks.append(
            _EffectSlot(deps=(), callback=lambda: None, cleanup=last_cleanup, pending=False)
        )
        renderer = RecordingRenderer()
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        with self.assertRaisesRegex(ValueError, "last cleanup failed"):
            reconciler.unmount()

        self.assertEqual(called, ["last", "first"])
        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertEqual(parent.hooks, [])

    def test_unbind_failure_still_disposes_slot_ref_and_children(self) -> None:
        parent, child = make_tree(lambda: None)
        slot = EventSlot(lambda: "old")
        parent.event_slots["on_click"] = (slot, "subscription")
        native_ref: Ref[object] = Ref("parent")
        parent.ref = native_ref
        renderer = RecordingRenderer()
        renderer.failing_unbind = "subscription"
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        with self.assertRaisesRegex(RuntimeError, "injected native unbind failure"):
            reconciler.unmount()

        self.assertIsNone(slot.invoke())
        self.assertIsNone(native_ref.current)
        self.assertEqual(parent.event_slots, {})
        self.assertTrue(child.disposed)
        self.assertEqual(renderer.unbound, ["subscription"])
        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertIsNone(reconciler.root)

    def test_child_destroy_failure_does_not_skip_parent_destroy(self) -> None:
        parent, child = make_tree(lambda: None)
        renderer = RecordingRenderer()
        renderer.failing_destroy = "child"
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        with self.assertRaisesRegex(RuntimeError, "injected native destroy failure"):
            reconciler.unmount()

        self.assertTrue(child.disposed)
        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertIsNone(reconciler.root)

    def test_repeated_clean_unmount_does_not_repeat_destroy(self) -> None:
        renderer = RecordingRenderer()
        reconciler = Reconciler(renderer)
        for _ in range(100):
            parent, child = make_tree(lambda: None)
            reconciler.root = parent
            reconciler.unmount()
            self.assertTrue(child.disposed)
        self.assertEqual(renderer.destroyed.count("child"), 100)
        self.assertEqual(renderer.destroyed.count("parent"), 100)


if __name__ == "__main__":
    unittest.main()
