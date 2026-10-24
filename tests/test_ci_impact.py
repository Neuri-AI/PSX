"""Failure-focused regression tests for the Native layout change-impact router."""

import unittest
from scripts.ci.impact import SUITES, classify


class RoutingTests(unittest.TestCase):
    def selected(self, *paths):
        return set(classify(list(paths))["selected"])

    def test_html_native_label_interactions_run_on_qt(self):
        self.assertEqual(self.selected("tests/test_qt_html_form_associations.py"), {"qt"})

    def test_missing_qt_image_fallback_is_executed(self):
        self.assertEqual(self.selected("tests/test_qt_missing_image_intrinsic.py"), {"qt"})

    def test_html_select_and_link_refresh_are_executed(self):
        self.assertEqual(self.selected("tests/test_html_select_options.py"), {"core", "qt", "kivy", "tkinter"})
        self.assertEqual(self.selected("tests/test_qt_link_refresh_navigation.py"), {"qt"})

    def test_html_radio_grouping_runs_on_native_backends(self):
        self.assertEqual(self.selected("tests/test_html_radio_grouping.py"), {"core", "qt", "kivy", "tkinter"})

    def test_html_form_content_regression_is_executed(self):
        self.assertEqual(self.selected("tests/test_html_form_content.py"), {"core", "qt", "kivy", "tkinter"})

    def test_html_form_input_regression_is_executed(self):
        from pathlib import Path
        self.assertEqual(self.selected("tests/test_html_form_input_events.py"), {"core", "qt", "kivy", "tkinter"})
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_html_form_input_events.py", workflow)

    def test_mixed_paragraph_text_regression_runs_in_core_validation(self):
        from pathlib import Path
        self.assertGreaterEqual(self.selected("tests/test_markup_inline_text_coalescing.py"), {"core", "headless", "qt", "kivy", "tkinter"})
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_markup_inline_text_coalescing.py", workflow)

    def test_documented_beginner_app_is_routed_to_real_qt_reproduction(self):
        expected = {"router", "qt"}
        for path in (
            "examples/documented_hello/main.py",
            "examples/documented_hello/settings/base.json",
            "examples/documented_hello/pyproject.toml",
            "tests/certification/verify_documented_hello.py",
            ".github/workflows/documented-example-reproduction.yml",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)
        self.assertEqual(
            self.selected("docs/public/getting-started/first-app.mdx"), set()
        )
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/documented-example-reproduction.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/certification/verify_documented_hello.py", workflow)
        self.assertIn("3.11", workflow)
        self.assertIn("3.12", workflow)

    def test_full_native_event_loop_and_resource_tests_route_to_all_consumers(self):
        expected = {"core", "headless", "qt", "kivy", "tkinter"}
        for path in (
            "tests/test_native_event_loop_process.py",
            "tests/certification/native_event_loop_child.py",
            "tests/test_native_supervised_restart.py",
            "tests/certification/native_supervised_child.py",
            "tests/test_native_refresh_resource_soak.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)
        self.assertEqual(
            self.selected(".github/workflows/cross-platform-native-reload.yml"),
            expected | {"router"},
        )

    def test_coordinated_refresh_stress_routes_every_mounted_backend(self):
        expected = {"core", "headless", "qt", "kivy", "tkinter"}
        self.assertEqual(self.selected("tests/test_native_coordinated_refresh.py"), expected)
        self.assertEqual(self.selected(".github/workflows/coordinated-refresh.yml"),
                         expected | {"router"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/coordinated-refresh.yml").read_text(encoding="utf-8")
        for backend in ("qt", "tk", "kivy"):
            self.assertIn(f"PSX_GRID_BACKEND={backend}", workflow)
        self.assertIn("tests/test_native_coordinated_refresh.py", workflow)

    def test_markup_styles_bind_without_bypassing_native_regression_suites(self):
        self.assertEqual(self.selected("tests/test_markup_css_binding.py"),
                         {"core", "headless", "qt", "kivy", "tkinter"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_markup_css_binding.py", workflow)
        self.assertIn("tests/test_css_markup_census.py", workflow)
        self.assertEqual(self.selected("tests/test_css_markup_census.py"),
                         {"core", "headless", "qt", "kivy", "tkinter"})

    def test_qt_form_baseline_regression_is_executed(self):
        self.assertEqual(self.selected("tests/sfle/test_qt_inline_form_baselines.py"), {"sfle", "qt"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/sfle/test_qt_inline_form_baselines.py", workflow)

    def test_qt_css_background_regression_is_executed_by_qt_job(self):
        self.assertEqual(self.selected("tests/test_qt_css_control_background.py"), {"qt"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_qt_css_control_background.py", workflow)

    def test_internal_css_foundations_route_to_executed_core_tests(self):
        self.assertEqual(self.selected("psx/css/properties.py"), {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"})
        self.assertEqual(self.selected("tests/css/test_properties.py"), {"core"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/css/test_properties.py", workflow)
        self.assertIn("tests/css/test_parser_and_cascade.py", workflow)
        self.assertEqual(self.selected("psx/css/parser.py"), {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"})
        self.assertEqual(self.selected("psx/css/cascade.py"), {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"})
        self.assertEqual(self.selected("psx/css/cache.py"), {"core"})
        self.assertIn("tests/css/test_cache.py", workflow)
        self.assertIn("tests/css/test_visual_values.py", workflow)
        self.assertEqual(self.selected("psx/css/visual_values.py"), {"core"})
        self.assertIn("tests/css/test_effects.py", workflow)
        self.assertIn("tests/css/test_property_catalog.py", workflow)
        self.assertIn("tests/css/test_catalog.py", workflow)
        self.assertEqual(self.selected("psx/css/catalog.py"), {"core"})
        self.assertIn("tests/css/test_tree.py", workflow)
        self.assertIn("tests/css/test_sources.py", workflow)
        self.assertIn("tests/css/test_context.py", workflow)
        self.assertIn("tests/css/test_geometry_handoff.py", workflow)
        self.assertIn("tests/css/test_box_flow_geometry.py", workflow)
        self.assertIn("tests/css/test_native_paint.py", workflow)
        self.assertEqual(self.selected("psx/css/native_paint.py"), {"core", "qt", "kivy", "tkinter"})
        self.assertEqual(self.selected("psx/css/geometry.py"), {"core"})
        self.assertEqual(self.selected("psx/css/context.py"), {"core"})
        self.assertEqual(self.selected("psx/css/sources.py"), {"core"})
        self.assertEqual(self.selected("psx/css/tree.py"), {"core"})
        self.assertEqual(self.selected("psx/css/effects.py"), {"core"})

    def test_block_flow_snapshots_run_all_native_geometry_consumers(self):
        expected = {"core", "sfle", "rust", "chromium", "headless",
                    "qt", "kivy", "tkinter"}
        for path in (
            "psx/sfle/flow_layout.py",
            "psx/sfle/display_context.py",
            "psx/sfle/measured_block_snapshot.py",
            "tests/sfle/test_measured_block_snapshot.py",
            "tests/sfle/test_flow_language_vectors.py",
            "tests/fixtures/flow_geometry_cases.json",
        ):
            self.assertEqual(self.selected(path), expected)
        self.assertEqual(
            self.selected("psx/sfle/headless_block_bridge.py"),
            {"core", "sfle", "headless"},
        )

    def test_css_display_context_routes_cinnamon_and_native_consumers(self):
        self.assertGreaterEqual(
            self.selected("psx/sfle/display_context.py"),
            {"sfle", "rust", "chromium", "headless"},
        )
        self.assertEqual(self.selected("tests/sfle/test_display_context.py"), {"sfle"})

    def test_block_flow_math_runs_pure_geometry_and_language_parity_gates(self):
        self.assertGreaterEqual(
            self.selected("psx/sfle/flow_layout.py"),
            {"sfle", "rust", "chromium", "headless"},
        )
        self.assertEqual(self.selected("tests/sfle/test_flow_layout.py"), {"sfle"})

    def test_incremental_cinnamon_routes_every_geometry_consumer(self):
        expected = {"core", "sfle", "rust", "chromium", "headless",
                    "qt", "kivy", "tkinter"}
        for path in (
            "psx/sfle/compute_alpha.py",
            "psx/sfle/engine.py",
            "psx/sfle/context_invalidation_plan.py",
            "psx/sfle/incremental_result_reuse.py",
            "tests/test_incremental_result_reuse.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)
        self.assertEqual(self.selected(
            "docs/architecture/canonical-box-geometry-implementation-evidence.md"
        ), set())
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/test_incremental_result_reuse.py", workflow)

    def test_expressive_composition_security_routing(self):
        self.assertEqual(self.selected("tests/test_expressive_composition_security.py"),
                         {"core", "headless"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_expressive_composition_security.py", workflow)

    def test_component_arrow_runtime_routes_to_core_and_headless(self):
        self.assertEqual(self.selected("tests/test_component_lexical_runtime.py"),
                         {"core", "headless"})

    def test_arrow_callback_paths_select_core_and_headless(self):
        self.assertEqual(self.selected("tests/test_arrow_callback_rendering.py"),
                         {"core", "headless"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_arrow_callback_rendering.py", workflow)

    def test_declarative_list_paths_run_in_core_and_headless(self):
        for path in ("tests/test_declarative_list_rendering.py",
                     "psx/markup/expressive_lower.py",
                     "psx/markup/expressive_runtime.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), {"core", "headless"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/test_declarative_list_rendering.py", workflow)

    def test_conditional_markup_routes_core_and_headless(self):
        for path in (
            "psx/markup/expressive_lower.py",
            "psx/markup/expressive_runtime.py",
            "tests/test_expressive_conditional_rendering.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), {"core", "headless"})
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/test_expressive_conditional_rendering.py", workflow)

    def test_expressive_markup_grammar_routes_real_core_and_headless(self):
        for path in (
            "psx/markup/expressive_syntax.py",
            "psx/markup/parser.py",
            "psx/markup/transform.py",
            "tests/test_expressive_markup_syntax.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), {"core", "headless"})
        self.assertEqual(
            self.selected("docs/architecture/expressive-markup-progress.md"), set()
        )
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/test_expressive_markup_syntax.py", workflow)

    def test_application_grid_settings_change_routes_all_native_consumers(self):
        self.assertGreaterEqual(self.selected('psx/app.py'),
                                {'core', 'qt', 'kivy', 'tkinter', 'headless'})
        self.assertEqual(self.selected('tests/test_grid_contract.py'),
                         {'core', 'qt', 'kivy', 'tkinter', 'headless'})
        self.assertEqual(self.selected('docs/architecture/responsive-grid-contract.md'), set())

    def test_headless_mounted_grid_routes_headless_validation(self):
        for path in ("psx/sfle/headless_grid_bridge.py", "tests/test_headless_grid_native_layout.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), {"core", "sfle", "headless"})

    def test_grid_native_commit_routes_all_geometry_consumers(self):
        expected = {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        for path in ("psx/sfle/grid_native_commit.py", "psx/sfle/native_grid_bridge.py",
                     "psx/sfle/grid_native_composition.py",
                     "psx/sfle/mixed_grid_native.py",
                     "psx/sfle/grid_flex_composition.py",
                     "tests/sfle/test_grid_native_commit.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)

    def test_grid_native_source_measurement_routes_all_geometry_consumers(self):
        expected = {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        for path in ("psx/sfle/grid_native_measurement.py",
                     "tests/sfle/test_grid_native_measurement.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)

    def test_grid_measurement_handoff_routes_all_geometry_consumers(self):
        expected = {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        for path in ("psx/sfle/grid_tree_measurement.py",
                     "tests/sfle/test_grid_tree_measurement.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)

    def test_grid_native_preflight_routes_all_geometry_consumers(self):
        expected = {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        for path in ("psx/sfle/grid_native_plan.py",
                     "tests/sfle/test_grid_native_plan.py"):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)

    def test_grid_row_solver_routes_both_language_parity_suites(self):
        expected = {"sfle", "rust"}
        for path in (
            "psx/sfle/grid_math.py",
            "rust/sfle-core/src/grid_math.rs",
            "tests/sfle/test_grid_math.py",
            "tests/fixtures/grid_row_packing.json",
            "tests/fixtures/grid_cross_axis.json",
                "tests/fixtures/grid_constraints.json",
                "tests/fixtures/grid_pixel_projection.json",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), expected)
        self.assertEqual(
            self.selected("docs/architecture/responsive-grid-mathematics.md"), set()
        )
        self.assertEqual(
            self.selected("psx/sfle/grid_math.py", "docs/architecture/README.md"),
            expected,
        )
        self.assertEqual(
            self.selected("psx/sfle/grid_math.py", "psx/renderers/kivy/kivy.py"),
            {"sfle", "rust", "kivy"},
        )

    def test_grid_contract_code_and_tests_route_to_executable_core_suite(self):
        self.assertGreaterEqual(
            self.selected("psx/core/grid_contract.py"),
            {"core", "headless", "qt", "kivy", "tkinter", "legacy"},
        )
        self.assertEqual(self.selected("tests/test_grid_contract.py"),
                         {"core", "qt", "kivy", "tkinter", "headless"})
        self.assertEqual(
            self.selected("docs/architecture/responsive-grid-contract.md"),
            set(),
        )
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(
                        encoding="utf-8")
        self.assertIn("tests/test_grid_contract.py", workflow)

    def test_public_census_changes_require_all_evidence_producers(self):
        expected = {"core", "qt", "kivy", "tkinter", "headless"}
        for path in (
            "tests/test_grid_contract.py",
            "tests/test_public_behavior_census.py",
            "tests/test_public_contract_census.py",
            "tests/test_public_property_validation.py",
            "tests/certification/public_behavior_census.py",
            "tests/certification/public_property_cases.py",
        ):
            self.assertEqual(self.selected(path), expected)

    def test_documentation_only_has_zero_tests(self):
        result = classify(["docs/architecture/sfle-f3-implementation.md", "README.md"])
        self.assertTrue(result["docs_only"])
        self.assertEqual(result["selected"], [])

    def test_markdown_outside_docs_is_still_documentation(self):
        self.assertEqual(self.selected("CHANGELOG.md"), set())

    def test_lowercase_markup_aliases_route_to_every_native_consumer(self):
        expected = {"core", "qt", "kivy", "tkinter", "headless"}
        self.assertGreaterEqual(self.selected("psx/core/registry.py"), expected)
        self.assertEqual(self.selected("tests/test_lowercase_markup_aliases.py"), expected)
        self.assertEqual(self.selected("docs/architecture/ARCHITECTURE_APPROVAL.md"), set())
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/native-layout-selective.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_lowercase_markup_aliases.py", workflow)

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

    def test_mounted_grid_lifecycle_runs_all_native_toolkits(self):
        self.assertEqual(self.selected("tests/test_mounted_grid_native_renderers.py"),
                         {"core", "qt", "kivy", "tkinter"})

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

    def test_canonical_tkinter_flex_changes_run_real_native_geometry_suite(self):
        self.assertEqual(
            self.selected("psx/sfle/tkinter_layout_bridge.py"),
            {"tkinter"},
        )
        self.assertEqual(
            self.selected("tests/test_tkinter_native_layout.py"),
            {"tkinter"},
        )

    def test_canonical_kivy_flex_changes_run_real_native_geometry_suite(self):
        self.assertEqual(
            self.selected("psx/sfle/kivy_layout_bridge.py"),
            {"kivy"},
        )
        self.assertEqual(
            self.selected("tests/test_kivy_native_layout.py"),
            {"kivy"},
        )

    def test_canonical_headless_flex_changes_run_mounted_geometry_suite(self):
        self.assertEqual(
            self.selected("psx/sfle/headless_layout_bridge.py"),
            {"headless"},
        )
        # The selector classifies this test module as core; the native
        # Headless job runs its own mounted suite for bridge source changes.
        self.assertEqual(
            self.selected("tests/test_headless_native_layout.py"),
            {"core"},
        )

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

    def test_shared_native_validation_workflow_selects_geometry_engines(self):
        expected = {"router", "core", "sfle", "rust", "qt", "kivy", "tkinter", "headless"}
        self.assertEqual(
            self.selected(".github/workflows/native-layout-selective.yml"),
            expected,
        )

    def test_shared_native_bridges_trigger_all_downstream_consumers(self):
        all_consumers = {"core", "headless", "qt", "kivy", "tkinter"}
        for filename in ("canonical_box_style.py",
                         "external_native_geometry_ports.py"):
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
        self.assertEqual(self.selected(".github/workflows/native-layout-selective.yml"),
                         {"router", "core", "sfle", "rust", "qt", "kivy", "tkinter", "headless"})

    def test_canonical_qt_flex_integration_routes_to_real_qt_suite(self):
        self.assertEqual(
            self.selected("psx/sfle/qt_layout_bridge.py"),
            {"qt"},
        )
        self.assertEqual(
            self.selected("tests/test_qt_native_component_lifecycle.py"),
            {"qt"},
        )

    def test_qt_layout_bridge_binding_parity_module_routes_to_qt_not_core(self):
        self.assertEqual(self.selected("tests/test_qt_native_component_lifecycle.py"), {"qt"})

    def test_qt_webview_extension_routes_to_qt(self):
        self.assertEqual(self.selected("psx/extensions/qt_webengine.py"), {"qt"})

    def test_workflow_affecting_browser_enables_chromium(self):
        self.assertEqual(
            self.selected(".github/workflows/sfle-chromium.yml"),
            {"router", "chromium"},
        )

    def test_headless_resource_baseline_routes_to_core_suite(self):
        self.assertEqual(self.selected("benchmarks/resource_baseline.py"), {"core"})
        self.assertEqual(self.selected("tests/test_resource_baseline.py"), {"core"})

    def test_test_only_change_runs_corresponding_family(self):
        self.assertEqual(self.selected("tests/test_kivy_renderer.py"), {"kivy"})
        self.assertEqual(self.selected("tests/browser/test_sfle_chromium.py"), {"chromium"})

    def test_old_and_new_rename_union(self):
        result = self.selected("psx/renderers/qt/old.py", "psx/renderers/kivy/new.py")
        self.assertEqual(result, {"qt", "kivy"})

    def test_mixed_docs_and_code_runs_code(self):
        self.assertEqual(self.selected("docs/guide.md", "psx/renderers/qt/button.py"), {"qt"})

    def test_broad_unsafe_changes_fail_open(self):
        self.assertTrue(classify(None)["full"])
        self.assertEqual(set(classify(None)["selected"]), set(SUITES))
        # Unknown changes must run every gate, including retired public APIs.
        self.assertTrue(classify(None, force_full=True)["full"])
        self.assertEqual(set(classify(None, force_full=True)["selected"]), set(SUITES))
        self.assertTrue(classify(["../hidden"])["full"])
        self.assertEqual(set(classify(["../hidden"])["selected"]), set(SUITES))
        self.assertTrue(classify([f"tests/t{i}.py" for i in range(300)])["full"])
        self.assertEqual(set(classify([f"tests/t{i}.py" for i in range(300)])["selected"]), set(SUITES))
        result = classify([".future-ci-extension"])
        self.assertTrue(result["full"])
        self.assertEqual(set(result["selected"]), set(SUITES))

    def test_explicit_full_overrides_documentation_only(self):
        result = classify(["docs/README.md"], force_full=True)
        self.assertFalse(result["docs_only"])
        self.assertEqual(set(result["selected"]), set(SUITES))


if __name__ == "__main__":
    unittest.main()


def test_coordinated_refresh_routes_to_all_native_renderer_consumers():
    from scripts.ci.impact import classify

    for changed in ("psx/devtools/coordinated_refresh.py", "tests/test_coordinated_refresh.py"):
        selected = set(classify([changed])["selected"])
        assert {"core", "qt", "kivy", "tkinter", "headless"} <= selected


def test_hook_remount_and_native_lifecycle_select_each_backend():
    from scripts.ci.impact import classify

    for changed in (
        'psx/core/reconcile.py', 'psx/core/hooks.py',
        'tests/test_component_remount.py', 'tests/test_native_coordinated_refresh.py',
    ):
        selected = set(classify([changed])['selected'])
        assert {'core', 'qt', 'kivy', 'tkinter', 'headless'} <= selected


def test_css_flex_geometry_changes_select_native_and_language_parity():
    from scripts.ci.impact import classify
    all_consumers = {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"}
    for path in ("psx/css/properties.py", "tests/css/test_parser_and_cascade.py",
                 "psx/sfle/native_layout_snapshot.py", "tests/test_native_layout_snapshot.py"):
        assert set(classify([path])["selected"]) == all_consumers
    assert set(classify(["psx/css/cache.py"])["selected"]) == {"core"}
    assert classify(["docs/css.mdx"])["selected"] == []
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    native = (root / ".github/workflows/native-layout-selective.yml").read_text()
    reload = (root / ".github/workflows/cross-platform-native-reload.yml").read_text()
    for name in ("tests/css/test_parser_and_cascade.py", "tests/test_native_layout_snapshot.py",
                 "tests/test_mounted_grid_native_renderers.py"):
        assert name in native
    assert "tests/test_native_coordinated_refresh.py" in reload
