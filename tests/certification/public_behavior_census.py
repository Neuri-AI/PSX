"""Source-derived census for the final public behavior acceptance gate.

This module intentionally makes no PASS claims. A scenario without native
JUnit evidence remains pending, even if a related lifecycle suite passed.
"""
from __future__ import annotations

import argparse
import json
from xml.etree import ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

BACKENDS = ("pyside6", "pyqt6", "pyqt5", "pyside2", "kivy", "tkinter", "headless")
PROPERTY_SCENARIOS = ("default", "valid_boundary", "live_update", "invalid_rejection", "native_readback")
EVENT_SCENARIOS = ("native_dispatch", "payload", "rebind", "disabled", "teardown")
STRUCTURAL_SCENARIOS = ("mount", "update", "reorder", "unmount")


@dataclass(frozen=True, order=True)
class Feature:
    component: str
    backend: str
    feature_kind: str
    feature_name: str
    scenario_id: str
    status: str = "pending"
    applicability: str = "review_required"


def inventory() -> tuple[Feature, ...]:
    """Derive the advertised surface from live contracts, not a curated list."""
    from psx.core.registry import builtin_component_registry
    from psx.core.layout_item import FLEX_ITEM_PROPS

    from tests.certification.native_component_matrix import native_certification_matrix

    definitions = builtin_component_registry().snapshot()
    native = {(cell.backend, cell.component): cell.status
              for cell in native_certification_matrix()}
    rows = []
    for component, definition in sorted(definitions.items()):
        contract = definition.contract
        if contract is None:
            # Fragment, Box and Native have no public ComponentContract.
            # Their lifecycle must not disappear from the coverage census.
            for backend in BACKENDS:
                family = "qt" if backend.startswith(("pyqt", "pyside")) else (
                    "tk" if backend == "tkinter" else backend)
                applicability = native[(family, component)]
                for operation in STRUCTURAL_SCENARIOS:
                    rows.append(Feature(component, backend, "lifecycle", operation,
                                        "native_behavior", applicability=applicability))
            continue
        properties = set(contract.properties)
        if component != "Flex":
            properties.update(FLEX_ITEM_PROPS)
        for backend in BACKENDS:
            family = "qt" if backend.startswith(("pyqt", "pyside")) else (
                "tk" if backend == "tkinter" else backend)
            applicability = native[(family, component)]
            rows.append(Feature(component, backend, "child_policy", contract.child_policy,
                                "validate", applicability=applicability))
            for prop in sorted(properties):
                for scenario in PROPERTY_SCENARIOS:
                    rows.append(Feature(component, backend, "property", prop, scenario,
                                        applicability=applicability))
            for event in sorted(contract.events):
                for scenario in EVENT_SCENARIOS:
                    rows.append(Feature(component, backend, "event", event, scenario,
                                        applicability=applicability))
            for operation in STRUCTURAL_SCENARIOS:
                rows.append(Feature(component, backend, "lifecycle", operation,
                                    "native_behavior", applicability=applicability))
    result = tuple(sorted(set(rows)))
    if len(result) != len(rows):
        raise ValueError("Duplicate public behavior census entry")
    return result


def validate_receipts(rows: tuple[Feature, ...], receipts: list[dict],
                      *, sha: str) -> dict:
    """Reject ungrounded, skipped, foreign-SHA and duplicate claimed passes."""
    if not sha or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("A full immutable lowercase commit SHA is required")
    keys = {(r.component, r.backend, r.feature_kind, r.feature_name, r.scenario_id) for r in rows}
    by_key = {}
    for receipt in receipts:
        key = tuple(receipt.get(k) for k in
                    ("component", "backend", "feature_kind", "feature_name", "scenario_id"))
        if key not in keys or key in by_key:
            raise ValueError(f"Unexpected or duplicate behavior receipt: {key}")
        status = receipt.get("status")
        if status not in ("executed_pass", "failed", "pending", "unsupported", "not_applicable"):
            raise ValueError(f"Invalid receipt status for {key}: {status}")
        if status == "executed_pass":
            if (receipt.get("sha") != sha or not receipt.get("test_id") or
                    not receipt.get("junit_artifact") or not receipt.get("environment")):
                raise ValueError(f"Unproven executed PASS for {key}")
            artifact = Path(receipt["junit_artifact"])
            if not artifact.is_file():
                raise ValueError(f"Missing JUnit artifact for {key}")
            matches = [case for case in ET.parse(artifact).getroot().iter("testcase")
                       if case.get("classname", "") + "::" + case.get("name", "")
                       == receipt["test_id"]]
            if len(matches) != 1 or any(
                matches[0].find(tag) is not None
                for tag in ("skipped", "failure", "error")
            ):
                raise ValueError(f"No unique successful JUnit assertion for {key}")
        if status in ("unsupported", "not_applicable") and not receipt.get("reason"):
            raise ValueError(f"Unexplained exclusion for {key}")
        by_key[key] = receipt
    pending = sum(1 for k in keys if k not in by_key or
                  by_key[k].get("status") == "pending")
    passes = sum(x.get("status") == "executed_pass" for x in by_key.values())
    failed = sum(x.get("status") == "failed" for x in by_key.values())
    return {"sha": sha, "total": len(keys), "pending": pending,
            "executed_pass": passes, "excluded": sum(
                x.get("status") in ("unsupported", "not_applicable") for x in by_key.values()),
            "failed": failed,
            "complete": pending == 0 and failed == 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = inventory()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([asdict(row) for row in rows], indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"public_behavior_rows": len(rows), "pending": len(rows)}))


if __name__ == "__main__":
    main()
