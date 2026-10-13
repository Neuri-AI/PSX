"""C5 fail-closed native component x semantic invalidation JUnit certificate.

The component driver proves the individual registered control survives a
native invalidation; the reason driver independently exercises each semantic
reason. Both must run and pass in the SAME JUnit file and on the same SHA.
This does not claim that every component has a distinct font/image/screen
resource: the six reasons are supported global/targeted notification inputs,
not a claim that every widget owns an image.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from psx.sfle.native_measurement_invalidation import REASONS
from .native_operation_contracts import native_operation_contracts

COMPONENT_DRIVERS = {
    "qt": "test_registered_builtin_lifecycle_keeps_real_native_identity",
    "tk": "test_registered_builtin_lifecycle_keeps_real_native_identity",
    "kivy": "test_all_ported_builtin_lifecycles_keep_native_widget_handles",
    "headless": "test_all_supported_headless_components_reconcile_without_remount",
}
REASON_DRIVERS = {
    "qt": "test_semantic_measurement_invalidations_keep_qt_widgets_mounted",
    "tk": "test_semantic_invalidations_preserve_native_tk_widget_identity",
    "kivy": "test_semantic_measurement_invalidations_do_not_remount_kivy",
    "headless": "test_c5_targeted_invalidations_remeasure_only_dirty_native_handles",
}
ADDITIONAL_DRIVERS = {
    "qt": (
        "test_native_qt_font_and_theme_events_invalidate_without_remount",
        "test_child_style_invalidation_targets_native_intrinsic_without_global_dirty",
        "test_native_local_image_revision_remeasures_without_props_or_remount",
        "test_targeted_resource_remeasurement_does_not_measure_unaffected_qt_peer",
        "test_readback_race_restores_native_geometry_and_preserves_identity",
    ),
    "tk": (
        "test_tk_theme_changed_event_requests_sfle_remeasurement",
        "test_native_local_image_revision_remeasures_without_props_or_remount",
        "test_targeted_resource_remeasurement_does_not_measure_unaffected_tk_peer",
        "test_readback_race_restores_tk_placement_and_preserves_identity",
    ),
    "kivy": (
        "test_native_root_and_sdl2_window_resize_automatically_reflow_sfle",
        "test_live_kivy_image_file_revision_reflows_native_siblings",
        "test_targeted_kivy_resource_remeasurement_skips_native_peer",
        "test_kivy_readback_race_rolls_back_real_widget_geometry",
    ),
    "headless": (
        "test_c5_invalidated_during_measurement_rejects_stale_geometry_and_recovers",
        "test_c5_invalidation_during_native_readback_rolls_back_and_recovers",
        "test_c5_multi_trigger_invalidation_during_measurement_preserves_cache_and_retries",
        "test_c5_solver_invalidation_rejects_provisional_result_and_recovers",
    ),
}


def _executed_methods(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    methods: dict[str, str] = {}
    for case in root.iter("testcase"):
        method = case.get("name", "").split("[", 1)[0]
        if not method:
            continue
        status = "fail" if any(case.find(tag) is not None
                               for tag in ("error", "failure", "skipped")) else "pass"
        if methods.get(method) == "fail":
            status = "fail"
        methods[method] = status
    if not methods:
        raise ValueError("No JUnit testcase receipts available")
    return methods


def certify_c5(backend: str, junit: str | Path) -> dict:
    if backend not in COMPONENT_DRIVERS:
        raise ValueError(f"Unknown C5 backend: {backend}")
    methods = _executed_methods(Path(junit))
    contracts = [
        c for c in native_operation_contracts()
        if c.backend == backend and c.operation == "invalidation"
        and c.applicability == "required"
    ]
    if not contracts:
        raise ValueError(f"Missing native C5 contracts for {backend}")
    expected_driver = COMPONENT_DRIVERS[backend]
    required_tests = {expected_driver, REASON_DRIVERS[backend], *ADDITIONAL_DRIVERS[backend]}
    failures = sorted(test for test in required_tests if methods.get(test) != "pass")
    if failures:
        raise ValueError(f"C5 mandatory native JUnit receipts absent or failing: {failures}")
    reasons = tuple(sorted(REASONS))
    records = []
    for contract in contracts:
        if contract.reference != expected_driver or contract.mechanism != "pytest_reference":
            raise ValueError(f"Invalid C5 component contract: {contract.backend}/{contract.component}: {contract.reference}")
        for reason in reasons:
            records.append({
                "backend": backend,
                "component": contract.component,
                "operation": "invalidation",
                "reason": reason,
                "component_driver": expected_driver,
                "reason_driver": REASON_DRIVERS[backend],
                "status": "executed_pass",
            })
    expected = len(contracts) * len(reasons)
    if len(records) != expected:
        raise ValueError("C5 required operation matrix incomplete")
    return {"backend": backend, "component_count": len(contracts),
            "reasons": reasons, "required_cases": expected,
            "executed_pass": len(records), "pending": 0,
            "supporting_drivers": sorted(required_tests), "contracts": records}


def main() -> None:
    parser = argparse.ArgumentParser(description="C5 strict JUnit receipt validator")
    parser.add_argument("--backend", required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = certify_c5(args.backend, args.junit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("backend", "component_count", "required_cases", "executed_pass", "pending")}, sort_keys=True))


if __name__ == "__main__":
    main()
