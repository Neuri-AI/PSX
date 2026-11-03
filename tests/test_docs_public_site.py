"""Regression tests for the F5.5 G2 structural site validator."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.docs.validate_public_site import TEMPLATE_FAMILIES, check, nav_pages


class PublicSiteTests(unittest.TestCase):
    def test_complete_site_structure(self):
        # The former docs/public site is no longer shipped. Exercise the
        # reusable validator against a complete site instead of that old path.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs.json").write_text(json.dumps({
                "$schema": "https://mintlify.com/docs.json", "name": "Velto",
                "theme": "mint", "colors": {"primary": "#123456"},
                "navigation": {"pages": ["introduction"]},
            }))
            page = '---\ntitle: "Welcome"\ndescription: "Intro"\n---\n# Intro\n'
            (root / "introduction.mdx").write_text(page)
            (root / "_templates").mkdir()
            for family in TEMPLATE_FAMILIES:
                (root / "_templates" / (family + ".mdx")).write_text(page)
            self.assertEqual(check(root), [])

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
