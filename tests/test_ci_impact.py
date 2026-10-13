"""Failure-focused regression tests for the Native layout change-impact router."""

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
            {"core", "qt", "kivy", "tkinter", "headless", "legacy"},
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

    def test_native_registry_coverage_is_not_skipped(self):
        self.assertIn("core", self.selected("psx/core/contracts.py"))

    def test_native_layout_backend_bridge_changes_execute_the_owner_toolkit(self):
        self.assertEqual(self.selected("psx/sfle/qt_layout_bridge.py"), {"qt"})
        self.assertEqual(self.selected("psx/sfle/kivy_layout_bridge.py"), {"kivy"})
        self.assertEqual(self.selected("psx/sfle/tkinter_layout_bridge.py"), {"tkinter"})
        self.assertEqual(self.selected("psx/sfle/headless_layout_bridge.py"), {"headless"})

    def test_native_measurement_changes_cover_their_toolkit_and_sfle(self):
        for filename, native in (
            ("qt_measurement.py", "qt"),
            ("kivy_measurement.py", "kivy"),
            ("tk_measurement.py", "tkinter"),
            ("headless_measurement.py", "headless"),
        ):
            self.assertEqual(
                self.selected(f"psx/sfle/{filename}"), {"sfle", native}
            )

    def test_shared_native_bridges_trigger_all_downstream_consumers(self):
        all_consumers = {"core", "headless", "qt", "kivy", "tkinter"}
        for filename in ("native_layout_snapshot.py", "external_native_geometry_ports.py"):
            self.assertEqual(self.selected(f"psx/sfle/{filename}"), all_consumers)

    def test_shared_width_dpi_and_capability_changes_reach_native_jobs(self):
        consumers = {"core", "qt", "kivy", "tkinter"}
        for filename in (
            "width_dependent_intrinsic_measurement.py",
            "native_component_capabilities.py",
            "native_pixel_space.py",
        ):
            self.assertEqual(self.selected(f"psx/sfle/{filename}"), consumers)

    def test_native_geometry_preserves_core_and_toolkit_regressions(self):
        self.assertGreaterEqual(
            self.selected("psx/sfle/native_geometry.py"),
            {"core", "sfle", "qt", "kivy", "tkinter", "headless"},
        )

    def test_flex_docs_delta_does_not_require_previous_green(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/flex-layout-contract-certification.yml").read_text(
                        encoding="utf-8")
        self.assertIn("const docsOnly = files.every(isDocumentation)", workflow)
        self.assertIn("run_contract', 'false'", workflow)
        self.assertNotIn("prior_green", workflow)
        self.assertIn("needs: changes", workflow)

    def test_native_layout_docs_only_precedes_prior_green_requirement(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertLess(
            workflow.index("if (docsOnly)"),
            workflow.index("const past = await github.rest.actions.listWorkflowRunsForRepo"))
        self.assertIn("const hasSuccessfulProductJob", workflow)
        self.assertIn("verifiedDelta = true", workflow)

    def test_product_workflows_use_shared_docs_only_gate(self):
        from pathlib import Path
        workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
        for name in ("sfle-chromium.yml", "sfle-native-matrix.yml",
                     "sfle-ui-certification.yml", "runtime-boundaries.yml"):
            with self.subTest(name=name):
                content = (workflows / name).read_text(encoding="utf-8")
                self.assertIn("uses: ./.github/workflows/docs-delta.yml", content)
                self.assertIn("needs: docs-impact", content)
                self.assertIn("if: needs.docs-impact.outputs.run_checks == 'true'", content)
        gate = (workflows / "docs-delta.yml").read_text(encoding="utf-8")
        self.assertIn("compareCommits", gate)
        self.assertIn("file.previous_filename", gate)
        self.assertIn("safelyComplete && paths.every(isDocs)", gate)

    def test_all_existing_main_ci_product_jobs_depend_on_change_gate(self):
        from pathlib import Path
        workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
        for name, prop, jobs in (
            ("ci.yml", "code", ("core", "pyside6", "package")),
            ("sfle-core.yml", "sfle", ("python-contracts", "rust-core",
                                       "differential", "native-wheel",
                                       "f2-migration-inventory")),
        ):
            text = (workflows / name).read_text(encoding="utf-8")
            for job in jobs:
                with self.subTest(name=name, job=job):
                    expected = ("  " + job + ":\\n    needs: changes\\n"
                                + "    if: needs.changes.outputs." + prop
                                + " == 'true'").replace("\\n", "\n")
                    self.assertIn(expected, text)

    def test_native_port_changes_include_wheels(self):
        self.assertIn("native", self.selected("psx/sfle/backend.py"))

    def test_selector_changes_only_test_selector(self):
        self.assertEqual(self.selected("scripts/ci/impact.py"), {"router"})

    def test_native_layout_workflow_must_exercise_qt_family_matrix(self):
        self.assertEqual(self.selected(".github/workflows/native-layout-selective.yml"), {"router", "qt"})

    def test_qt_layout_bridge_binding_parity_module_routes_to_qt_not_core(self):
        self.assertEqual(self.selected("tests/test_qt_native_component_lifecycle.py"), {"qt"})

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
        # Unknown changes must run every gate, including retired public APIs.
        self.assertEqual(set(classify(None, force_full=True)["selected"]), set(SUITES))
        self.assertEqual(set(classify(["../hidden"])["selected"]), set(SUITES))
        self.assertEqual(set(classify([f"tests/t{i}.py" for i in range(300)])["selected"]), set(SUITES))
        self.assertEqual(self.selected(".future-ci-extension"), set(SUITES))

    def test_explicit_full_overrides_documentation_only(self):
        result = classify(["docs/README.md"], force_full=True)
        self.assertFalse(result["docs_only"])
        self.assertEqual(set(result["selected"]), set(SUITES))


if __name__ == "__main__":
    unittest.main()
