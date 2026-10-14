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
# Cross-property interactions that cannot be inferred from isolated validation.
# New semantic coupling requires an explicit reviewed entry, not every cartesian pair.
INTERACTIONS = {
    "Input": (("enabled", "on_change"), ("read_only", "on_change"),
              ("password", "value"), ("placeholder", "value")),
    "TextArea": (("read_only", "on_change"), ("value", "layout_width")),
    "Slider": (("min", "max"), ("value", "step"), ("enabled", "on_change")),
    "SpinBox": (("value", "min"), ("value", "max"), ("step", "decimals")),
    "Select": (("options", "value"), ("enabled", "on_change")),
    "Scroll": (("direction", "enabled"), ("width", "height")),
    "Flex": (("direction", "wrap"), ("justify_content", "gap")),
    "Button": (("enabled", "on_click"),),
    "Checkbox": (("enabled", "on_change"),),
    "Switch": (("enabled", "on_change"),),
}

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
            if component not in ("Flex", "Grid", "GridItem"):
                props.update(FLEX_ITEM_PROPS)
            rows.append(Feature(component, CONTRACT, "child_policy",
                                contract.child_policy, "validate", applicability="shared"))
            if component in ("Grid", "GridItem"):
                for scenario in ("builder", "markup", "direct_element",
                                 "registry", "invalid_property", "key_identity",
                                 "invalid_children"):
                    rows.append(Feature(component, CONTRACT, "public_api",
                                        "declaration", scenario, applicability="shared"))
            if component == "Grid":
                for scenario in ("canonical_pixel_grammar", "axis_gap_inheritance",
                                 "invalid_primary_gap"):
                    rows.append(Feature(component, CONTRACT, "interaction",
                                        "gap_normalization", scenario, applicability="shared"))
            elif component == "GridItem":
                for scenario in ("breakpoint_inheritance", "responsive_overflow_rejection",
                                 "responsive_valid_combination"):
                    rows.append(Feature(component, CONTRACT, "interaction",
                                        "span_offset", scenario, applicability="shared"))
            if component == "GridItem":
                for scenario in ("inclusive_threshold", "custom_thresholds",
                                 "inherited_values", "invalid_width",
                                 "invalid_thresholds", "application_settings",
                                 "application_settings_invalid",
                                 "application_settings_isolated"):
                    rows.append(Feature(component, CONTRACT, "interaction",
                                        "responsive_resolution", scenario,
                                        applicability="shared"))
            if component in ("Grid", "GridItem"):
                for scenario in ("headless_fail_closed", "pyside6_fail_closed",
                                 "pyqt6_fail_closed", "pyqt5_fail_closed",
                                 "pyside2_fail_closed", "tkinter_fail_closed",
                                 "kivy_fail_closed"):
                    rows.append(Feature(component, CONTRACT, "interaction",
                                        "unsupported_mount", scenario,
                                        applicability="shared"))
            if component == "Grid":
                for scenario in ("geometry_readback", "resize_reflow", "keyed_reorder", "teardown"):
                    rows.append(Feature(component, "headless", "interaction",
                                        "native_root", scenario, applicability="partial_native"))
            if component == "GridItem":
                rows.append(Feature(component, "headless", "interaction",
                                    "native_child", "geometry_readback", applicability="partial_native"))
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
                                    "classification_review", applicability=status))
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
                native_props = set(contract.properties) - set(contract.events)
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
                for a, b in INTERACTIONS.get(component, ()):
                    available = set(contract.properties) | (FLEX_ITEM_PROPS if component != "Flex" else set())
                    if a not in available or b not in available:
                        raise ValueError(f"Stale feature interaction {component}: {a}/{b}")
                    rows.append(Feature(component, backend, "interaction",
                                        f"{a}__{b}", "paired_native", applicability=status))
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



def collect_executed_receipts(rows: tuple[Feature, ...], artifacts: tuple[Path, ...],
                              *, sha: str, environment: str) -> list[dict]:
    """Import only directly asserted features from successful real JUnit runs.

    No implicit attribution from test names, components or inherited adapters.
    A testcase claiming an unknown feature is an error, never ignored.
    """
    expected = {feature_key(row): row for row in rows}
    observed: list[dict] = []
    for artifact in artifacts:
        cases = _executed_receipts(artifact)
        for test_id, case in cases.items():
            features = case["features"]
            if len(features) != len(set(features)):
                raise ValueError(f"Duplicate assertions in {test_id}")
            for key in features:
                row = expected.get(key)
                if row is None:
                    raise ValueError(f"Unknown source feature assertion: {key}")
                if not case["passed"]:
                    # Never promote a failed or skipped testcase to green.
                    status = "failed"
                else:
                    status = "executed_pass"
                observed.append({
                    **dict(zip(KEY_FIELDS, key)), "status": status,
                    "sha": sha, "test_id": test_id,
                    "junit_artifact": str(artifact), "environment": environment,
                })
    return observed



def merge_executed_manifests(rows: tuple[Feature, ...], manifests: tuple[Path, ...],
                             *, sha: str, require_complete: bool = False,
                             require_contract_components: tuple[str, ...] = ()) -> dict:
    """Recheck original JUnit files after downloading per-platform artifacts.

    Receipt manifests are transport metadata, never independently trusted
    proof. Each reference is resolved next to its manifest and authenticated
    again against the original testcase assertion property.
    """
    receipts: list[dict] = []
    if not manifests:
        raise ValueError("Final aggregation requires executed receipt manifests")
    for manifest in manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("receipts"), list):
            raise ValueError(f"Invalid receipt manifest: {manifest}")
        if data.get("summary", {}).get("sha") != sha:
            raise ValueError(f"Foreign-SHA evidence manifest: {manifest}")
        for original in data["receipts"]:
            receipt = dict(original)
            if "junit_artifact" in receipt:
                supplied = Path(receipt["junit_artifact"])
                if supplied.is_absolute() or ".." in supplied.parts:
                    raise ValueError(f"Unsafe referenced JUnit path: {supplied}")
                # Uploaded GitHub artifacts can be unpacked in per-job folders.
                resolved = manifest.parent / supplied
                if not resolved.is_file():
                    resolved = manifest.parent / supplied.name
                receipt["junit_artifact"] = str(resolved)
            receipts.append(receipt)
    report = validate_receipts(rows, receipts, sha=sha)
    if require_contract_components:
        required_components = set(require_contract_components)
        scoped_rows = {feature_key(row) for row in rows
                       if row.backend == CONTRACT and row.component in required_components}
        found_components = {row.component for row in rows if row.backend == CONTRACT
                            and row.component in required_components}
        if found_components != required_components or not scoped_rows:
            raise ValueError(f"Unknown contract certification components: "
                             f"{sorted(required_components - found_components)}")
        passed = {feature_key(receipt) for receipt in receipts
                  if receipt.get("status") == "executed_pass"}
        missing = scoped_rows - passed
        report["contract_scope"] = {
            "components": sorted(required_components), "required": len(scoped_rows),
            "executed_pass": len(scoped_rows - missing), "pending": len(missing),
            "complete": not missing,
        }
        if missing:
            raise ValueError(f"Incomplete component contract certification: "
                             f"{sorted(missing)[:12]} ({len(missing)} missing)")
    if require_complete and not report["complete"]:
        raise ValueError(
            f"Final public behavior certificate incomplete: "
            f"pending={report['pending']} failed={report['failed']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--junit", type=Path, action="append", default=[])
    parser.add_argument("--sha")
    parser.add_argument("--environment")
    parser.add_argument("--receipt-file", type=Path, action="append", default=[])
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--require-contract-component", action="append", default=[])
    args = parser.parse_args()
    rows = inventory()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([asdict(row) for row in rows],
                                   indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    counts = Counter(row.backend for row in rows)
    if args.junit and args.receipt_file:
        parser.error("Select --junit or --receipt-file, not both")
    if args.receipt_file:
        if not args.sha:
            parser.error("--receipt-file requires --sha")
        report = merge_executed_manifests(
            rows, tuple(args.receipt_file), sha=args.sha,
            require_complete=args.require_complete,
            require_contract_components=tuple(args.require_contract_component))
        args.out.with_name(args.out.stem + "-final-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.require_contract_component:
            # Preserve full global audit in JSON, but emit the *requested*
            # scoped acceptance result instead of unrelated historic gaps.
            print(json.dumps({"certificate": "scoped_public_contract",
                              "sha": report["sha"],
                              "contract_scope": report["contract_scope"],
                              "global_inventory_artifact":
                                  args.out.with_name(args.out.stem + "-final-report.json").name},
                             sort_keys=True))
        else:
            print(json.dumps(report, sort_keys=True))
    elif args.junit:
        if not args.sha or not args.environment:
            parser.error("--junit requires --sha and --environment")
        receipts = collect_executed_receipts(
            rows, tuple(args.junit), sha=args.sha, environment=args.environment)
        report = validate_receipts(rows, receipts, sha=args.sha)
        report_path = args.out.with_name(args.out.stem + "-receipts.json")
        report_path.write_text(json.dumps({"summary": report, "receipts": receipts},
                                          indent=2) + "\n", encoding="utf-8")
        if args.require_complete and not report["complete"]:
            raise ValueError(f"Public behavior coverage incomplete: {report}")
        # Per-backend collection is an evidence producer, not a global release gate.
        # Keep the complete coverage report in the receipts manifest.
        print(json.dumps({"certificate": "receipt_collection",
                          "sha": report["sha"],
                          "executed_pass": report["executed_pass"],
                          "failed": report["failed"],
                          "receipt_manifest": report_path.name}, sort_keys=True))
    else:
        # Inventory generation must not imply that every unexecuted cell is a
        # failure of the incremental capability under test.
        print(json.dumps({"certificate": "inventory_generated",
                          "public_behavior_rows": len(rows),
                          "by_backend": dict(sorted(counts.items()))},
                         sort_keys=True))


if __name__ == "__main__":
    main()
