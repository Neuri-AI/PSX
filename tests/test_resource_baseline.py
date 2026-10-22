"""Baseline probes are measurement tools, not native leak certification."""
import unittest

from benchmarks.resource_baseline import run, sample


class ResourceBaselineTests(unittest.TestCase):
    def test_headless_workloads_emit_real_memory_and_latency_observations(self):
        report = run(nodes=3, cycles=4, warmup=1)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(len(report["measurements"]), 4)
        for case in report["measurements"]:
            self.assertEqual(case["cycles"], 4)
            self.assertGreaterEqual(case["mean_ms"], 0)
            self.assertGreaterEqual(case["p95_ms"], 0)
            self.assertIsInstance(case["traced_retained_delta_bytes"], int)
            self.assertTrue(case["checkpoints"])
            self.assertIn("rss_peak_bytes", case["process_memory"])
            self.assertIn("uss_bytes", case["process_memory"])

    def test_invalid_workloads_are_rejected(self):
        for kwargs in ({"nodes": 0}, {"cycles": 0}, {"warmup": -1},
                       {"scenario": "unsupported"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                sample(**kwargs)


if __name__ == "__main__":
    unittest.main()
