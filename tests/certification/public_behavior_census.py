"""Code-derived, nonduplicated public behavior census and executed evidence.

Portable validation runs once per component/property in the core, while native
readback, updates and events run once per supported backend. A successful JUnit
testcase is never proof unless it also carries an explicit assertion receipt.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

BACKENDS = ("pyside6", "pyqt6", "pyqt5", "pyside2", "kivy", "tkinter", "headless")
CONTRACT = "contract"
PROPERTY_SCENARIOS = ("default", "valid_boundary", "invalid_rejection")
NATIVE_PROPERTY_SCENARIOS = ("live_update", "native_readback")
EVENT_SCENARIOS = ("native_dispatch", "payload", "rebind", "disabled", "teardown")
STRUCTURAL_SCENARIOS = ("mount", "update", "reorder", "unmount")
RECEIPT_PROPERTY = "psx_verified_feature"
KEY_FIELDS = ("component", "backend", "feature_kind", "feature_name", "scenario_id")


@dataclass(frozen=True, order=True)
class Feature:
    component: str
    backend: str
    feature_kind: str
    feature_name: str
    scenario_id: str
    status: str = "pending"
    applicability: str = "review_required"


def feature_key(value: Feature | dict) -> tuple[str, ...]:
    if isinstance(value, Feature):
        return tuple(getattr(value, field) for field in KEY_FIELDS)
    return tuple(value.get(field) for field in KEY_FIELDS)


def inventory() -> tuple[Feature, ...]:
    """No unreviewed exclusions: native suitability comes from G2's registry."""
    from psx.core.registry import builtin_component_registry
    from psx.core.props import FLEX_ITEM_PROPS
    from tests.certification.native_component_matrix import native_certification_matrix

    definitions = builtin_component_registry().snapshot()
    native = {(cell.backend, cell.component): cell.status
              for cell in native_certification_matrix()}
    rows: list[Feature] = []
    for component, definition in sorted(definitions.items()):
        contract = definition.contract
        if contract is not None:
            props = set(contract.properties)
            if component != "Flex":
                props.update(FLEX_ITEM_PROPS)
            rows.append(Feature(component, CONTRACT, "child_policy",
                                contract.child_policy, "validate", applicability="shared"))
            for prop in sorted(props):
                for scenario in PROPERTY_SCENARIOS:
                    rows.append(Feature(component, CONTRACT, "property", prop,
                                        scenario, applicability="shared"))
        for backend in BACKENDS:
            family = ("qt" if backend.startswith(("pyqt", "pyside")) else
                      "tk" if backend == "tkinter" else backend)
            status = native[(family, component)]
            if status == "unported":
                rows.append(Feature(component, backend, "capability", "native_host",
                                    "reject_unsupported", applicability=status))
                continue
            if status == "external_port_required":
                rows.append(Feature(component, backend, "capability", "external_port",
                                    "ownership_and_geometry", applicability=status))
                continue
            if status == "transparent":
                for operation in STRUCTURAL_SCENARIOS:
                    rows.append(Feature(component, backend, "lifecycle", operation,
                                        "transparent_boundary", applicability=status))
                continue
            if status != "native":
                raise ValueError(f"Unclassified backend status: {backend}/{component}={status}")
            if contract is not None:
                # Layout metadata is applied by SFLE, not forwarded to leaf controls.
                native_props = set(contract.properties)
                if component != "Flex":
                    native_props.update(FLEX_ITEM_PROPS)
                for prop in sorted(native_props):
                    for scenario in NATIVE_PROPERTY_SCENARIOS:
                        rows.append(Feature(component, backend, "property", prop,
                                            scenario, applicability=status))
                for event in sorted(contract.events):
                    for scenario in EVENT_SCENARIOS:
                        rows.append(Feature(component, backend, "event", event,
                                            scenario, applicability=status))
            for operation in STRUCTURAL_SCENARIOS:
                rows.append(Feature(component, backend, "lifecycle", operation,
                                    "native_behavior", applicability=status))
    if len(set(rows)) != len(rows):
        raise ValueError("Duplicate functional census entry")
    return tuple(sorted(rows))


def assert_feature(request, feature: Feature, condition: bool, detail: str = "") -> None:
    """Emit a JUnit feature assertion receipt only after an actual assertion."""
    assert condition, detail or f"Failed functional assertion: {feature_key(feature)}"
    request.node.user_properties.append((RECEIPT_PROPERTY, json.dumps(
        dict(zip(KEY_FIELDS, feature_key(feature))), sort_keys=True)))


def _executed_receipts(artifact: Path) -> dict[str, dict[str, object]]:
    if not artifact.is_file():
        raise ValueError(f"Missing JUnit artifact: {artifact}")
    result = {}
    for case in ET.parse(artifact).getroot().iter("testcase"):
        key = case.get("classname", "") + "::" + case.get("name", "")
        if not case.get("classname") or not case.get("name") or key in result:
            raise ValueError(f"Malformed or duplicate JUnit testcase: {key}")
        properties = []
        for prop in case.findall("./properties/property"):
            if prop.get("name") == RECEIPT_PROPERTY:
                try:
                    properties.append(feature_key(json.loads(prop.get("value", ""))))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid assertion receipt in {key}") from exc
        result[key] = {
            "passed": not any(case.find(tag) is not None
                              for tag in ("skipped", "failure", "error")),
            "features": properties,
        }
    return result


def validate_receipts(rows: tuple[Feature, ...], receipts: list[dict], *,
                      sha: str) -> dict:
    """Fail closed on missing, reused, or nonexecuted semantic assertions."""
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("A full immutable lowercase commit SHA is required")
    expected = {feature_key(row): row for row in rows}
    if len(expected) != len(rows):
        raise ValueError("Duplicate source census feature")
    seen = set()
    junit_cache: dict[Path, dict] = {}
    counts = {"executed_pass": 0, "unsupported": 0, "not_applicable": 0,
              "failed": 0, "pending": 0}
    for receipt in receipts:
        key = feature_key(receipt)
        if key not in expected or key in seen:
            raise ValueError(f"Unexpected or duplicate behavior receipt: {key}")
        seen.add(key)
        status = receipt.get("status")
        if status not in (*counts,):
            raise ValueError(f"Invalid receipt status: {status}")
        row = expected[key]
        if status in ("unsupported", "not_applicable"):
            if not receipt.get("reason") or not receipt.get("reviewed_by"):
                raise ValueError(f"Unreviewed exclusion: {key}")
            # No positive capability can be excluded merely to get GREEN.
            if status == "unsupported" and row.applicability != "unported":
                raise ValueError(f"Supported capability excluded: {key}")
            if status == "not_applicable" and row.applicability == "native":
                raise ValueError(f"Required native behavior excluded: {key}")
        if status in ("executed_pass", "unsupported"):
            if (receipt.get("sha") != sha or not receipt.get("test_id") or
                    not receipt.get("junit_artifact") or not receipt.get("environment")):
                raise ValueError(f"Missing bound executable evidence: {key}")
            path = Path(receipt["junit_artifact"])
            if path not in junit_cache:
                junit_cache[path] = _executed_receipts(path)
            result = junit_cache[path].get(receipt["test_id"])
            if not result or not result["passed"] or key not in result["features"]:
                raise ValueError(f"Missing successful feature assertion in JUnit: {key}")
            if result["features"].count(key) != 1:
                raise ValueError(f"Duplicate feature assertion in JUnit: {key}")
            if status == "executed_pass" and row.applicability == "unported":
                raise ValueError(f"Unported native behavior cannot PASS: {key}")
        counts[status] += 1
    counts["pending"] += len(expected) - len(seen)
    return {"sha": sha, "total": len(expected), **counts,
            "excluded": counts["unsupported"] + counts["not_applicable"],
            "complete": counts["pending"] == 0 and counts["failed"] == 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = inventory()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([asdict(row) for row in rows],
                                   indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    counts = Counter(row.backend for row in rows)
    print(json.dumps({"public_behavior_rows": len(rows), "pending": len(rows),
                      "by_backend": dict(sorted(counts.items()))}))


if __name__ == "__main__":
    main()
