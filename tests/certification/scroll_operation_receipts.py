"""Fail-closed, backend-specific executed Scroll operation certification.

Only testcase receipts from the expected native test module are accepted.
A passing unrelated component, backend or skipped test cannot certify Scroll.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

# Operations are stable semantic names, never implementation milestone IDs.
# Every mandatory row has its own behavior-specific executable test.
REQUIRED = {
    "qt": {
        "viewport_clipping_offsets": "test_native_scroll_overflow_offsets_and_viewport_clipping",
        "nested_wheel_chaining": "test_nested_qt_scroll_residual_routes_to_parent_once",
        "keyboard_boundary": "test_native_scroll_keyboard_moves_and_releases_at_boundary",
        "reflow_focus_identity": "test_scroll_reflow_preserves_native_offset_focus_and_widget_identity",
        "native_failure_rollback": "test_scroll_failed_native_commit_restores_offsets_and_extent",
        "unmount_lifecycle": "test_scroll_unmount_releases_native_viewport",
        "disabled_axes_after_scroll": "test_scroll_disabled_axes_reset_existing_offsets",
    },
    "tk": {
        "viewport_clipping_offsets": "test_native_scroll_overflow_offsets_and_canvas_clipping",
        "nested_wheel_chaining": "test_nested_native_tk_wheel_chains_only_remaining_pixels",
        "keyboard_boundary": "test_native_tk_wheel_and_keyboard_offset_readback",
        "reflow_identity": "test_scroll_reflow_keeps_logical_offset_and_native_identity",
        "native_failure_rollback": "test_scroll_failed_commit_restores_tk_scrollregion_and_offsets",
        "unmount_lifecycle": "test_scroll_unmount_releases_tk_canvas",
        "disabled_axes_after_scroll": "test_scroll_disabled_axes_reset_existing_tk_offsets",
    },
    "kivy": {
        "viewport_clipping_offsets": "test_scroll_overflow_native_extent_and_logical_offsets",
        "nested_wheel_touch": "test_native_kivy_wheel_and_nested_edge_chaining",
        "mounted_viewport": "test_scroll_basic_sfle_viewport_and_explicit_content_root",
        "resize_reflow": "test_scroll_mounted_reflow_preserves_logical_offsets",
        "native_failure_rollback": "test_scroll_native_kivy_failure_restores_offsets",
        "unmount_lifecycle": "test_scroll_unmount_detaches_kivy_viewport",
    },
    "headless": {
        "offset_clamping": "test_scroll_offset_clamps_each_axis_and_preserves_engine_boxes",
        "independent_axes": "test_scroll_axes_are_independent",
        "disabled_input_residual": "test_disabled_scroll_consumes_nothing_and_returns_event_to_parent",
        "nested_offsets": "test_nested_scroll_frames_keep_offsets_independent",
        "shrink_reset": "test_content_shrinking_to_viewport_resets_offsets_without_relayout",
    },
}
TEST_MODULE = {
    "qt": "tests.test_pyside6_native_layout",
    "tk": "tests.test_tkinter_native_layout",
    "kivy": "tests.test_kivy_native_layout",
    "headless": "tests.test_scroll_offsets",
}
NOT_APPLICABLE = {
    "headless": ("native_focus", "native_kinetic_touch", "native_widget_unmount"),
}


def certify_scroll_receipts(backend: str, junit: str | Path) -> dict:
    if backend not in REQUIRED:
        raise ValueError(f"Unknown Scroll certification backend: {backend!r}")
    root = ET.parse(junit).getroot()
    observed: dict[tuple[str, str], list[str]] = {}
    for case in root.iter("testcase"):
        name = case.get("name", "")
        classname = case.get("classname", "")
        if not name or not classname:
            continue
        operation = name.split("[", 1)[0]
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            state = "failed"
        else:
            state = "passed"
        observed.setdefault((classname, operation), []).append(state)
    records = []
    for operation, test_name in REQUIRED[backend].items():
        receipts = [
            status for (classname, name), states in observed.items()
            if name == test_name and (
                classname == TEST_MODULE[backend]
                or classname.startswith(TEST_MODULE[backend] + ".")
            )
            for status in states
        ]
        if receipts and all(state == "passed" for state in receipts):
            status = "executed_pass"
        elif receipts:
            status = "executed_fail"
        else:
            status = "missing"
        records.append({
            "backend": backend, "component": "Scroll",
            "operation": operation, "test": test_name, "status": status,
        })
    for operation in NOT_APPLICABLE.get(backend, ()):
        records.append({
            "backend": backend, "component": "Scroll",
            "operation": operation, "test": None, "status": "not_applicable",
            "reason": "Headless has no interactive native widget or focus.",
        })
    failures = [record for record in records
                if record["status"] not in ("executed_pass", "not_applicable")]
    if failures:
        raise ValueError(f"Missing/failing executed Scroll operation receipts: {failures}")
    return {
        "backend": backend, "component": "Scroll",
        "required": len(REQUIRED[backend]),
        "executed_pass": len(REQUIRED[backend]),
        "not_applicable": len(NOT_APPLICABLE.get(backend, ())),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=tuple(REQUIRED), required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = certify_scroll_receipts(args.backend, args.junit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in
                      ("backend", "required", "executed_pass", "not_applicable")}))


if __name__ == "__main__":
    main()
