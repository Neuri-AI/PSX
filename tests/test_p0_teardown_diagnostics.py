"""P0 H-MEM-01: renderer-free teardown probes.

Run: python -m unittest discover -s tests -p test_p0_teardown_diagnostics.py -v

The expectedFailure case documents a known source-indicated risk without
making the default test suite fail before an owner-approved C07 fix.
An unexpected success means the cleanup behavior has improved; review and
remove the decorator when the new behavior is certified.
"""

from __future__ import annotations

import unittest

from psx.core.hooks import _EffectSlot
from psx.core.instance import MountedInstance
from psx.core.reconcile import Reconciler
from psx.core.vnode import create_element


class RecordingRenderer:
    def __init__(self) -> None:
        self.destroyed: list[object] = []

    def destroy(self, handle: object) -> None:
        self.destroyed.append(handle)

    def invalidate_layout(self) -> None:
        pass

    def schedule_ui(self, callback: object) -> None:
        pass


def make_tree(cleanup):
    """Construct a mounted component boundary without any GUI toolkit."""
    parent = MountedInstance(node=create_element("P0Parent"), parent=None, handle="parent")
    child = MountedInstance(node=create_element("P0Child"), parent=parent, handle="child")
    parent.children.append(child)
    parent.hooks.append(_EffectSlot(deps=(), callback=lambda: None, cleanup=cleanup, pending=False))
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

    @unittest.expectedFailure
    def test_throwing_hook_still_releases_all_native_handles(self) -> None:
        """Target C07 contract: cleanup errors must not strand native handles.

        CURRENT SOURCE BEHAVIOR: dispose_hooks raises before _unmount descends
        into child native handles. This test intentionally fails until fixed.
        """
        def bad_cleanup() -> None:
            raise RuntimeError("P0 injected cleanup failure")

        parent, child = make_tree(bad_cleanup)
        renderer = RecordingRenderer()
        reconciler = Reconciler(renderer)
        reconciler.root = parent

        try:
            reconciler.unmount()
        except RuntimeError as exc:
            self.assertEqual(str(exc), "P0 injected cleanup failure")

        self.assertEqual(renderer.destroyed, ["child", "parent"])
        self.assertTrue(child.disposed)
        self.assertIsNone(reconciler.root)


if __name__ == "__main__":
    unittest.main()
