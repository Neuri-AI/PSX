"""Regression tests for the F5.5 G2 structural site validator."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.docs.validate_public_site import check, nav_pages


class PublicSiteTests(unittest.TestCase):
    def test_site_structure(self):
        self.assertEqual(check(), [])

    def test_navigation_recursive(self):
        self.assertEqual(nav_pages({"groups": [{"group": "A", "pages": ["a", "b"]}]}),
                         ["a", "b"])

    def test_missing_page_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs.json").write_text(json.dumps({
                "$schema": "https://mintlify.com/docs.json", "name": "Velto",
                "theme": "mint", "colors": {"primary": "#123456"},
                "navigation": {"pages": ["introduction", "missing"]},
            }))
            (root / "introduction.mdx").write_text(
                '---\ntitle: "Welcome"\ndescription: "Intro"\n---\n# Intro\n'
            )
            self.assertTrue(any("missing" in error for error in check(root)))

    def test_broken_link_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs.json").write_text(json.dumps({
                "$schema": "https://mintlify.com/docs.json", "name": "Velto",
                "theme": "mint", "colors": {"primary": "#123456"},
                "navigation": {"pages": ["introduction"]},
            }))
            (root / "introduction.mdx").write_text(
                '---\ntitle: "Welcome"\ndescription: "Intro"\n---\n'
                '# Intro\n[broken](/does-not-exist)\n'
            )
            self.assertTrue(any("unresolved local link" in error for error in check(root)))


if __name__ == "__main__":
    unittest.main()
