"""Pure-Python probe invariants; do not need a running SDL window."""
from __future__ import annotations

import gc
import unittest
import weakref

from scripts.p0_kivy_heap_ownership import (
    checkpoint_histogram, referrer_summary, tracked_type, type_label,
)


class HeapOwnershipProbeTests(unittest.TestCase):
    def test_expired_proxy_does_not_break_histogram(self) -> None:
        class Referent:
            pass

        referent = Referent()
        expired = weakref.proxy(referent)
        del referent
        gc.collect()
        # type(proxy) and its label may be inspected safely.
        self.assertIn("ProxyType", type_label(expired))
        self.assertFalse(tracked_type(expired))
        self.assertEqual(checkpoint_histogram([expired, {}, {}]).get("builtins.dict"), 2)
        self.assertEqual(referrer_summary([expired]), [])

    def test_referrer_output_does_not_include_repr(self) -> None:
        class Sample:
            pass

        # No matching psx/kivy labels, so no object content should be emitted.
        target = Sample()
        self.assertEqual(referrer_summary([target]), [])
        self.assertFalse(tracked_type(target))


if __name__ == "__main__":
    unittest.main()
