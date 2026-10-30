"""Classify Native layout changes into the smallest *safe* GitHub Actions test set.

Stdlib-only: called by the lightweight CI router before installing toolkits.
A missing, truncated or ambiguous change set fails open to full validation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import PurePosixPath

SUITES = (
    "router", "core", "sfle", "rust", "chromium", "qt", "kivy",
    "tkinter", "headless", "native", "legacy",
)


def _is_docs(path: str) -> bool:
    return path == "README.md" or path.startswith("docs/") or (
        path.endswith(".md") and not path.startswith(".github/")
    )


def _classify_path(path: str) -> set[str]:
    if path.startswith("examples/documented_hello/") or path in {
        "tests/certification/verify_documented_hello.py",
        ".github/workflows/documented-example-reproduction.yml",
    }:
        return {"router", "qt"}
    if path == ".github/workflows/development-reload-certification.yml":
        return {"router", "core", "headless", "qt", "kivy", "tkinter"}
    if path in {
        "tests/test_native_event_loop_process.py",
        "tests/certification/native_event_loop_child.py",
        "tests/test_native_supervised_restart.py",
        "tests/certification/native_supervised_child.py",
        "tests/test_native_refresh_resource_soak.py",
    }:
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == ".github/workflows/cross-platform-native-reload.yml":
        return {"router", "core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/test_html_select_options.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path == "tests/test_qt_missing_image_intrinsic.py":
        return {"qt"}
    if path == "tests/test_qt_link_refresh_navigation.py":
        return {"qt"}
    if path == "tests/test_html_radio_grouping.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path == "tests/test_html_form_content.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path == "tests/test_html_form_input_events.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path == "tests/test_markup_inline_text_coalescing.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/test_native_coordinated_refresh.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == ".github/workflows/coordinated-refresh.yml":
        return {"router", "core", "headless", "qt", "kivy", "tkinter"}
    if path == "benchmarks/resource_baseline.py":
        return {"core"}
    if path in ("benchmarks/grid_resize_profile.py", "benchmarks/grid_resize_interactive.py"):
        return {"qt", "tkinter"}
    if path in ("scripts/ci/impact.py", "tests/test_ci_impact.py") or path.startswith("scripts/ci/"):
        return {"router"}
    if path in ("tests/certification/qt_kivy_css_native_raster.py",
                "tests/certification/qt_kivy_native_text_metrics.py",
                ".github/workflows/kivy-retina-css-parity.yml"):
        # Native raster fixture exercises both painters, not only CSS parsing.
        return {"router", "qt", "kivy"}
    if path.startswith(".github/workflows/"):
        # A routing change must test the selector. Targeted workflows also
        # certify their own affected suite, not all of F2 by default.
        result = {"router"}
        name = PurePosixPath(path).name
        if name == "native-layout-selective.yml":
            # Changes to the shared Native layout workflow must exercise the Qt parity
            # matrix; don't certify its new required job with router-only CI.
            result.update({"core", "sfle", "rust", "qt", "kivy", "tkinter", "headless"})
        elif name == "sfle-chromium.yml":
            result.add("chromium")
        elif name == "sfle-ui-certification.yml":
            result.update({"qt", "kivy", "tkinter"})
        elif name == "sfle-native-matrix.yml":
            result.add("native")
        elif name == "sfle-core.yml":
            result.update({"sfle", "rust"})
        elif name == "grid-resize-performance.yml":
            result.update({"qt", "tkinter"})
        elif name == "ci.yml":
            result.add("core")
        return result
    if path == "tests/sfle/test_qt_inline_form_baselines.py":
        return {"sfle", "qt"}
    if path == "tests/test_viewport_lengths.py":
        return {"core", "sfle", "rust", "qt", "kivy", "tkinter", "headless"}
    if path == "tests/test_grid_html_parent.py":
        return {"qt"}
    if path == "tests/test_qt_html_form_associations.py":
        return {"qt"}
    if path in ("tests/test_qt_css_control_background.py", "tests/test_qt_semantic_border_scope.py", "tests/test_qt_scroll_wheel_continuity.py", "tests/test_qt_native_chart_refresh.py"):
        return {"qt"}
    if path == "psx/renderers/kivy/css_cursor.py" or path in (
        "tests/test_kivy_css_cursor.py",
        "tests/test_kivy_css_border_retina.py",
    ):
        return {"kivy"}
    if path in ("psx/renderers/tkinter/rounded_surface.py",
                "tests/test_native_rounded_card_visual.py"):
        # The visual raster comparison runs in the Qt job but exercises the
        # Tk implementation too; never route these changes to Tk alone.
        return {"qt", "tkinter"}
    if path in (
        "psx/css/cursor.py",
        "tests/css/test_cursor_shape_mapping.py",
    ):
        return {"core", "qt", "kivy", "tkinter"}
    if path == "psx/css/native_paint.py" or path == "tests/css/test_native_paint.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path in ("psx/css/properties.py", "psx/css/parser.py", "psx/css/cascade.py", "psx/css/markup.py", "tests/css/test_parser_and_cascade.py"):
        # CSS display/Flex vocabulary drives all layout engines and native adapters.
        return {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"}
    if path in ("psx/sfle/native_layout_snapshot.py", "tests/test_native_layout_snapshot.py"):
        # Immutable CSS-backed Cinnamon geometry affects every native consumer.
        return {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"}
    if path == "psx/css/inheritance.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path.startswith("psx/css/") or path.startswith("tests/css/"):
        return {"core"}
    if path == "pyproject.toml" or path in ("setup.cfg", "setup.py"):
        return {"core", "sfle", "rust", "qt", "kivy", "tkinter", "native"}
    if path == "rust/sfle-core/src/grid_math.rs":
        # This isolated mathematical contract is exercised by Rust and
        # Python fixtures; it does not yet change native geometry.
        return {"sfle", "rust"}
    if path.startswith("rust/sfle-core/"):
        return {"sfle", "rust", "chromium", "native"}
    if path in (
        "tests/test_css_cursor_native_adapter.py",
        "tests/test_css_auto_margin_native.py",
    ):
        return {"qt", "kivy", "tkinter"}
    if path == "tests/test_mounted_grid_native_renderers.py":
        return {"core", "qt", "kivy", "tkinter"}
    if path in ("psx/sfle/headless_grid_bridge.py", "tests/test_headless_grid_native_layout.py"):
        return {"core", "sfle", "headless"}
    if path in ("psx/sfle/grid_native_commit.py", "psx/sfle/native_grid_bridge.py",
                 "psx/sfle/grid_native_composition.py",
                 "psx/sfle/mixed_grid_native.py",
                 "psx/sfle/grid_flex_composition.py",
                 "tests/sfle/test_grid_flex_measurement_reuse.py",
                 "tests/sfle/test_grid_native_commit.py",
                 "tests/sfle/test_nested_grid_content_width.py",
                 "psx/sfle/grid_native_measurement.py", "tests/sfle/test_grid_native_measurement.py",
                 "psx/sfle/grid_tree_measurement.py", "tests/sfle/test_grid_tree_measurement.py"):
        return {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
    if path == "psx/sfle/grid_native_plan.py":
        return {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
    if path == "psx/sfle/grid_math.py":
        return {"sfle", "rust"}
    if path in ("psx/sfle/compute_alpha.py", "psx/sfle/engine.py",
                "psx/sfle/context_invalidation_plan.py",
                "psx/sfle/incremental_result_reuse.py",
                "tests/test_incremental_result_reuse.py"):
        return {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"}
    if path in (
        "psx/sfle/measured_block_snapshot.py",
        "psx/sfle/flow_layout.py",
        "psx/sfle/display_context.py",
        "tests/sfle/test_measured_block_snapshot.py",
        "tests/sfle/test_flow_language_vectors.py",
        "tests/fixtures/flow_geometry_cases.json",
    ):
        return {"core", "sfle", "rust", "chromium", "headless", "qt", "kivy", "tkinter"}
    if path == "psx/sfle/headless_block_bridge.py":
        return {"core", "sfle", "headless"}
    if path.startswith("psx/sfle/"):
        name = PurePosixPath(path).name
        # Production Native layout bridges must route to the real toolkit consumer, not
        # only to the neutral SFLE engine and browser oracle.
        if name == "qt_layout_bridge.py":
            return {"qt"}
        if name == "kivy_layout_bridge.py":
            return {"kivy"}
        if name == "tkinter_layout_bridge.py":
            return {"tkinter"}
        if name == "headless_layout_bridge.py":
            return {"headless"}
        if name in ("qt_measurement.py", "qt_worker_dispatch.py"):
            return {"sfle", "qt"}
        if name == "kivy_measurement.py":
            return {"sfle", "kivy"}
        if name == "tk_measurement.py":
            return {"sfle", "tkinter"}
        if name == "headless_measurement.py":
            return {"sfle", "headless"}
        if name in ("native_layout_snapshot.py", "canonical_box_style.py",
                    "external_native_geometry_ports.py"):
            return {"core", "headless", "qt", "kivy", "tkinter"}
        if name in ("width_dependent_intrinsic_measurement.py", "native_component_capabilities.py",
                    "native_pixel_space.py"):
            return {"core", "qt", "kivy", "tkinter"}
        if name in ("adapter_contract.py", "worker_lifecycle.py", "native_geometry.py",
                    "native_measurement.py", "native_lifecycle.py"):
            return {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        if name in ("backend.py", "native_loader.py"):
            return {"sfle", "rust", "native"}
        return {"sfle", "rust", "chromium", "headless"}
    if path.startswith("psx/renderers/qt/"):
        return {"qt"}
    if path == "psx/extensions/qt_webengine.py":
        return {"qt"}
    if path.startswith("psx/renderers/kivy/"):
        return {"kivy"}
    if path.startswith("psx/renderers/tkinter/"):
        return {"tkinter"}
    if path.startswith("psx/renderers/components/") or path.startswith("psx/renderers/base"):
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path == "psx/renderers/headless.py":
        return {"headless"}
    if path.startswith("psx/renderers/"):
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path == "psx/app.py":
        # Application-level Grid settings affect portable resolution and every
        # backend consumer even before native Grid geometry ships.
        return {"core", "headless", "qt", "kivy", "tkinter", "legacy"}
    if path == "tests/test_css_markup_census.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/test_component_css_inheritance.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "psx/css/inheritance.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/test_markup_css_binding.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/test_lowercase_markup_aliases.py":
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path in ("psx/__init__.py", "psx/core/native.py") or path.startswith("psx/core/"):
        return {"core", "headless", "qt", "kivy", "tkinter", "legacy"}
    if path in ("psx/core/reconcile.py", "psx/core/hooks.py", "tests/test_component_remount.py", "tests/test_native_coordinated_refresh.py"):
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path.startswith("psx/devtools/") or path == "tests/test_coordinated_refresh.py":
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path.startswith("psx/markup/") or path in ("tests/test_expressive_markup_syntax.py", "tests/test_expressive_conditional_rendering.py", "tests/test_declarative_list_rendering.py", "tests/test_arrow_callback_rendering.py", "tests/test_component_lexical_runtime.py", "tests/test_expressive_composition_security.py"):
        return {"core", "headless"}
    if path.startswith("psx/"):
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path == "tests/sfle/test_grid_native_plan.py":
        return {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
    if path in ("tests/fixtures/grid_row_packing.json",
                "tests/fixtures/grid_cross_axis.json",
                "tests/fixtures/grid_constraints.json",
                "tests/fixtures/grid_pixel_projection.json",
                "tests/sfle/test_grid_math.py"):
        return {"sfle", "rust"}
    if path.startswith("tests/browser/"):
        return {"chromium"}
    if path.startswith("tests/ui/"):
        return {"qt", "kivy", "tkinter"}
    if path.startswith("tests/sfle/"):
        if path == "tests/sfle/test_kivy_scroll_extent_projection.py":
            return {"sfle", "kivy"}
        if "qt" in path:
            return {"sfle", "qt"}
        return {"sfle"}
    if path.startswith("tests/interop/"):
        if "native_wheel" in path or "frozen" in path:
            return {"native"}
        return {"rust", "sfle"}
    if path in (
        "tests/test_grid_contract.py",
        "tests/test_public_behavior_census.py",
        "tests/test_public_contract_census.py",
        "tests/test_public_property_validation.py",
    ) or path.startswith("tests/certification/public_"):
        # Public-census assertions and its schema require receipts from every
        # backend, even after a previously green partial-PR optimization.
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path.startswith("tests/"):
        name = PurePosixPath(path).name
        if "kivy" in name:
            return {"kivy"}
        if "tkinter" in name or name.startswith("test_tk"):
            return {"tkinter"}
        if "pyqt" in name or "pyside" in name or "_qt_" in name:
            return {"qt"}
        return {"core"}
    if path.startswith("examples/") or path.startswith("scripts/"):
        return {"core"}
    # Unrecognized code/configuration: run all current product gates.
    return set(SUITES)


def classify(files: list[str] | None, *, force_full: bool = False) -> dict[str, object]:
    if force_full or not files or len(files) >= 300 or any(
        not isinstance(p, str) or not p or p.startswith("/") or ".." in PurePosixPath(p).parts
        for p in files
    ):
        selected = set(SUITES)
        why = "explicit full certification" if force_full else "missing, unsafe or truncated diff"
        return {
            "docs_only": False, "full": True,
            "selected": sorted(selected),
            "reason": why,
            "changed": files or [],
        }

    normalized = sorted(set(files))
    if all(_is_docs(p) for p in normalized):
        return {
            "docs_only": True, "full": False, "selected": [],
            "reason": "documentation-only; no product tests",
            "changed": normalized,
        }

    selection = set()
    causes = []
    for path in normalized:
        if _is_docs(path):
            continue
        groups = _classify_path(path)
        selection.update(groups)
        causes.append(f"{path}: {','.join(sorted(groups))}")
    # A path outside the reviewed routing map fails open to every product
    # suite. Treat that equivalently to an explicit full run so that the
    # final public-behavior aggregator cannot be silently omitted.
    full = selection == set(SUITES)
    return {
        "docs_only": False, "full": full,
        "selected": sorted(selection),
        "reason": "; ".join(causes),
        "changed": normalized,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-json", required=True)
    parser.add_argument("--github-output")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    with open(args.changed_json, encoding="utf-8") as stream:
        changed = json.load(stream)
    if not isinstance(changed, list):
        changed = None
    result = classify(changed, force_full=args.full)
    print(json.dumps(result, indent=2))
    output = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            for suite in SUITES:
                stream.write(f"{suite}={str(suite in result['selected']).lower()}\n")
            stream.write(f"docs_only={str(result['docs_only']).lower()}\n")
            stream.write(f"full={str(result['full']).lower()}\n")
            stream.write(f"selected={','.join(result['selected'])}\n")


if __name__ == "__main__":
    main()
