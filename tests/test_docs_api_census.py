"""G1 public export audit regression checks; does not certify native behavior."""
import unittest
from pathlib import Path
from scripts.docs.api_census import ROOT, census


class ApiCensusTests(unittest.TestCase):
    def test_pinned_snapshot_matches_current_root_exports(self):
        import json
        snapshot = json.loads((ROOT / "docs/architecture/f5-5-api-exports.json").read_text())
        actual = census((ROOT / "psx/__init__.py").read_text())
        self.assertEqual(actual, snapshot)

    def test_rejects_duplicate_exports(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            census('from .example import A\n__all__ = ["A", "A"]')

    def test_rejects_unresolved_exports(self):
        with self.assertRaisesRegex(ValueError, "without an explicit"):
            census('__all__ = ["Missing"]')


if __name__ == "__main__":
    unittest.main()
