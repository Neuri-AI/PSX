"""Unit tests for the P0 retained-resource trend summary."""
from __future__ import annotations

import unittest

from scripts.p0_memory_soak_report import markdown, summarize


def sample(cycles: int, rss: int | None, count: int, active: int) -> dict:
    return {
        "cycles": cycles,
        "rss_bytes": rss,
        "tracemalloc_current_bytes": 100 + count,
        "retained_instances": count,
        "retained_widgets": count,
        "active_event_slots": active,
    }


class SoakReportTests(unittest.TestCase):
    def test_deltas_include_first_to_last_and_tail(self) -> None:
        data = {
            "backend": "kivy", "python": "3.13", "cycles": 1000,
            "status": "investigate_retention",
            "samples": [
                sample(250, 1000, 1, 0),
                sample(500, 1300, 2, 1),
                sample(750, 1700, 3, 2),
                sample(1000, 2400, 5, 3),
            ],
        }
        summary = summarize(data)
        self.assertEqual(summary["first_to_last_deltas_bytes_or_counts"]["rss_bytes"], 1400)
        self.assertEqual(summary["tail_half_deltas_bytes_or_counts"]["retained_widgets"], 2)
        self.assertEqual(summary["final_active_event_slots"], 3)
        self.assertIn("kivy", markdown(summary))

    def test_no_rss_is_preserved_as_unavailable(self) -> None:
        data = {
            "backend": "tkinter", "python": "3.10", "cycles": 500,
            "status": "no_sustained_growth_detected_in_sample",
            "samples": [sample(250, None, 0, 0), sample(500, None, 0, 0)],
        }
        summary = summarize(data)
        self.assertIsNone(summary["first_to_last_deltas_bytes_or_counts"]["rss_bytes"])
        self.assertIn("N/A", markdown(summary))

    def test_single_sample_does_not_claim_a_trend(self) -> None:
        data = {
            "backend": "pyside6", "python": "3.13", "cycles": 250,
            "status": "no_sustained_growth_detected_in_sample",
            "samples": [sample(250, 1000, 0, 0)],
        }
        with self.assertRaisesRegex(ValueError, "At least two"):
            summarize(data)


if __name__ == "__main__":
    unittest.main()
