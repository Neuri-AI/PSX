"""Source-derived census for the final public behavior acceptance gate.

This module intentionally makes no PASS claims. A scenario without native
JUnit evidence remains pending, even if a related lifecycle suite passed.
"""
from __future__ import annotations

import argparse
import json
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


def inventory() -> tuple[Feature, ...]:
    """Derive the advertised surface from live contracts, not a curated list."""
    from psx.core.registry import builtin_component_registry
    from psx.core.layout_item import FLEX_ITEM_PROPS

    definitions = builtin_component_registry().snapshot()
    rows = []
    for component, definition in sorted(definitions.items()):
        contract = definition.contract
        if contract is None:
            # Fragment, Box and Native have no public ComponentContract.
            # Their lifecycle must not disappear from the coverage census.
            for backend in BACKENDS:
                for operation in STRUCTURAL_SCENARIOS:
                    rows.append(Feature(component, backend, "lifecycle", operation, "native_behavior"))
            continue
        properties = set(contract.properties)
        if component != "Flex":
            properties.update(FLEX_ITEM_PROPS)
        for backend in BACKENDS:
            rows.append(Feature(component, backend, "child_policy", contract.child_policy, "validate"))
            for prop in sorted(properties):
                for scenario in PROPERTY_SCENARIOS:
                    rows.append(Feature(component, backend, "property", prop, scenario))
            for event in sorted(contract.events):
                for scenario in EVENT_SCENARIOS:
                    rows.append(Feature(component, backend, "event", event, scenario))
            for operation in STRUCTURAL_SCENARIOS:
                rows.append(Feature(component, backend, "lifecycle", operation, "native_behavior"))
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
            # This does not independently authenticate JUnit files. Until an
            # executing verifier checks the artifact, the row stays pending.
            raise ValueError(f"Unverified JUnit assertion for {key}")
        if status in ("unsupported", "not_applicable") and not receipt.get("reason"):
            raise ValueError(f"Unexplained exclusion for {key}")
        by_key[key] = receipt
    pending = sum(1 for k in keys if k not in by_key or
                  by_key[k].get("status") == "pending")
    return {"sha": sha, "total": len(keys), "pending": pending,
            "claimed_pass": 0, "excluded": sum(
                x.get("status") in ("unsupported", "not_applicable") for x in by_key.values()),
            "failed": sum(x.get("status") == "failed" for x in by_key.values()),
            "complete": False}


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
