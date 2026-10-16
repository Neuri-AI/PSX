"""Coverage assertions for declared public APIs and component metadata."""
import unittest
from scripts.docs.full_api_audit import collect


class DeclaredPublicSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = collect()

    def test_root_consistency(self):
        from psx import __all__
        self.assertEqual(set(self.report["modules"]["psx"]), set(__all__))
        self.assertEqual(len(__all__), 56)

    def test_every_explicit_export_has_trace(self):
        for module, names in self.report["modules"].items():
            for name in names:
                with self.subTest(symbol=f"{module}.{name}"):
                    record = self.report["symbols"][f"{module}.{name}"]
                    self.assertIn(record["kind"], {"class", "callable", "constant"})
                    if record["kind"] != "constant":
                        self.assertIsNotNone(record["implementation"])

    def test_registered_component_contracts(self):
        components = self.report["registered_components"]
        for name in ("Grid", "GridItem", "Flex", "Text", "Button", "Scroll"):
            with self.subTest(component=name):
                self.assertIn(name, components)
                contract = components[name]["contract"]
                self.assertIsNotNone(contract)
                self.assertIsInstance(contract["child_policy"], str)
                self.assertIsInstance(contract["properties"], list)
                self.assertIsInstance(contract["events"], list)

    def test_internal_box_not_root_export(self):
        self.assertIn("Box", self.report["registered_components"])
        self.assertFalse(self.report["registered_components"]["Box"]["public_root_export"])


if __name__ == "__main__":
    unittest.main()
