"""Baseline probes are measurement tools, not native leak certification."""
import unittest

from benchmarks.resource_baseline import run, sample, make_renderer
from unittest.mock import patch
from psx.sfle.engine import PythonLayoutEngine


class ResourceBaselineTests(unittest.TestCase):
    def test_headless_workloads_emit_real_memory_and_latency_observations(self):
        report = run(nodes=3, cycles=4, warmup=1, engines=('python',))
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
            self.assertIn("rss_live_bytes", case["process_memory"])
            self.assertGreaterEqual(case["cpu_total_ms"], 0)
            self.assertGreaterEqual(case["wall_total_ms"], 0)
            for checkpoint in case["checkpoints"]:
                self.assertIn("rss_live_bytes", checkpoint["process_memory"])
                self.assertIn("uss_bytes", checkpoint["process_memory"])

    def test_rust_selection_never_silently_falls_back_to_python(self):
        with patch('benchmarks.resource_baseline.load_layout_engine', return_value=PythonLayoutEngine()):
            with self.assertRaisesRegex(RuntimeError, 'Requested Cinnamon rust'):
                make_renderer('rust')

    def test_invalid_workloads_are_rejected(self):
        for kwargs in ({"nodes": 0}, {"cycles": 0}, {"warmup": -1},
                       {"scenario": "unsupported"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                sample(**kwargs)


if __name__ == "__main__":
    unittest.main()


class ResourceSoakContractTests(unittest.TestCase):
    def test_checkpoint_intervals_and_teardown_are_recorded_for_longer_probe(self):
        result = sample(nodes=4, cycles=12, warmup=2, engine="python")
        self.assertEqual([item["cycle"] for item in result["checkpoints"]], [3, 6, 9, 12])
        self.assertEqual(result["cycles"], 12)
        self.assertIsInstance(result["traced_after_teardown_bytes"], int)
        self.assertTrue(all(item["gc_objects"] > 0 for item in result["checkpoints"]))
        self.assertGreaterEqual(result["process_memory"]["rss_peak_bytes"] or 0, 0)
