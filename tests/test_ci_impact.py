"""Failure-focused regression tests for the F3 change-impact router."""

import unittest
from scripts.ci.impact import SUITES, classify


class RoutingTests(unittest.TestCase):
    def selected(self, *paths):
        return set(classify(list(paths))["selected"])

    def test_documentation_only_has_zero_tests(self):
        result = classify(["docs/architecture/sfle-f3-implementation.md", "README.md"])
        self.assertTrue(result["docs_only"])
        self.assertEqual(result["selected"], [])

    def test_markdown_outside_docs_is_still_documentation(self):
        self.assertEqual(self.selected("CHANGELOG.md"), set())

    def test_python_component_registry_affects_all_native_backends(self):
        self.assertGreaterEqual(
            self.selected("psx/core/registry.py"),
            {"core", "qt", "kivy", "tkinter", "headless"},
        )

    def test_qt_only_does_not_run_rust_or_other_toolkits(self):
        self.assertEqual(self.selected("psx/renderers/qt/button.py"), {"qt"})

    def test_kivy_only(self):
        self.assertEqual(self.selected("psx/renderers/kivy/scroll.py"), {"kivy"})

    def test_tk_only(self):
        self.assertEqual(self.selected("psx/renderers/tkinter/scroll.py"), {"tkinter"})

    def test_headless_only(self):
        self.assertEqual(self.selected("psx/renderers/headless.py"), {"headless"})

    def test_shared_scroll_involves_all_backends(self):
        self.assertGreaterEqual(
            self.selected("psx/renderers/components/scroll.py"),
            {"core", "qt", "kivy", "tkinter", "headless"},
        )

    def test_geometry_projection_involves_real_ui(self):
        self.assertGreaterEqual(
            self.selected("psx/sfle/native_geometry.py"),
            {"sfle", "qt", "kivy", "tkinter"},
        )

    def test_engine_geometry_runs_chromium_differential(self):
        self.assertGreaterEqual(
            self.selected("psx/sfle/compute_alpha.py"),
            {"sfle", "rust", "chromium"},
        )

    def test_rust_change_runs_native_packaging(self):
        self.assertGreaterEqual(
            self.selected("rust/sfle-core/src/compute_layout.rs"),
            {"sfle", "rust", "chromium", "native"},
        )

    def test_g2_registry_coverage_is_not_skipped(self):
        self.assertIn("core", self.selected("psx/core/contracts.py"))

    def test_native_port_changes_include_wheels(self):
        self.assertIn("native", self.selected("psx/sfle/backend.py"))

    def test_selector_changes_only_test_selector(self):
        self.assertEqual(self.selected("scripts/ci/impact.py"), {"router"})

    def test_f3_workflow_only_tests_router(self):
        self.assertEqual(self.selected(".github/workflows/f3-selective.yml"), {"router"})

    def test_workflow_affecting_browser_enables_chromium(self):
        self.assertEqual(
            self.selected(".github/workflows/sfle-chromium.yml"),
            {"router", "chromium"},
        )

    def test_test_only_change_runs_corresponding_family(self):
        self.assertEqual(self.selected("tests/test_kivy_renderer.py"), {"kivy"})
        self.assertEqual(self.selected("tests/browser/test_sfle_chromium.py"), {"chromium"})

    def test_old_and_new_rename_union(self):
        result = self.selected("psx/renderers/qt/old.py", "psx/renderers/kivy/new.py")
        self.assertEqual(result, {"qt", "kivy"})

    def test_mixed_docs_and_code_runs_code(self):
        self.assertEqual(self.selected("docs/guide.md", "psx/renderers/qt/button.py"), {"qt"})

    def test_broad_unsafe_changes_fail_open(self):
        self.assertEqual(set(classify(None)["selected"]), set(SUITES))
        self.assertEqual(set(classify(["../hidden"])["selected"]), set(SUITES))
        self.assertEqual(set(classify([f"tests/t{i}.py" for i in range(300)])["selected"]), set(SUITES))
        self.assertEqual(self.selected(".future-ci-extension"), set(SUITES))

    def test_explicit_full_overrides_documentation_only(self):
        result = classify(["docs/README.md"], force_full=True)
        self.assertFalse(result["docs_only"])
        self.assertEqual(set(result["selected"]), set(SUITES))


if __name__ == "__main__":
    unittest.main()
