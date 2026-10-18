"""Regression tests for P0 memory instrument accuracy (no native toolkit)."""
from __future__ import annotations

import gc
import unittest
import weakref

from psx.core.instance import MountedInstance
from scripts.p0_memory_soak import mounted_instance_snapshot


class MemorySoakProbeTests(unittest.TestCase):
    def test_dead_weak_proxy_does_not_crash_snapshot(self) -> None:
        class Target:
            pass

        target = Target()
        dead_proxy = weakref.proxy(target)
        del target
        gc.collect()

        # Unlike type(), isinstance() dereferences a dead weak proxy.
        with self.assertRaises(ReferenceError):
            isinstance(dead_proxy, MountedInstance)

        mounted = MountedInstance(node=object(), parent=None)
        result = mounted_instance_snapshot([dead_proxy, object(), mounted])
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], mounted)

    def test_snapshot_does_not_count_foreign_widget_or_proxy(self) -> None:
        class ForeignWidget:
            pass

        other = ForeignWidget()
        proxy = weakref.proxy(other)
        mounted = MountedInstance(node=object(), parent=None)
        self.assertEqual(mounted_instance_snapshot([other, proxy, mounted]), [mounted])


if __name__ == "__main__":
    unittest.main()
