"""Regression guard for root-export documentation coverage."""
import unittest

from scripts.docs.validate_api_reference import check


class ApiReferenceCoverageTests(unittest.TestCase):
    def test_root_exports_in_index(self):
        check()


if __name__ == "__main__":
    unittest.main()
