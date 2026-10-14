"""Fail-closed tests for normalized public behavior and assertion-bound JUnit."""
from __future__ import annotations

from dataclasses import asdict
import json
from xml.etree import ElementTree as ET
import pytest

from tests.certification.public_behavior_census import (
    BACKENDS, CONTRACT, RECEIPT_PROPERTY, Feature, assert_feature,
    feature_key, inventory, validate_receipts,
)

SHA = "a" * 40


def test_source_derived_inventory_separates_shared_and_native():
    from psx.core.registry import builtin_component_registry
    from psx.core.props import FLEX_ITEM_PROPS
    from tests.certification.native_component_matrix import native_certification_matrix

    definitions = builtin_component_registry().snapshot()
    records = inventory()
    assert len(records) == len(set(records))
    assert {row.component for row in records} == set(definitions)
    assert {row.backend for row in records} == {*BACKENDS, CONTRACT}
    assert all(row.status == "pending" for row in records)
    native = {(cell.backend, cell.component): cell.status
              for cell in native_certification_matrix()}
    for component, definition in definitions.items():
        contract = definition.contract
        shared = [r for r in records if r.backend == CONTRACT and r.component == component]
        if contract is None:
            assert not shared
        else:
            advertised = set(contract.properties)
            if component not in ("Flex", "Grid", "GridItem"):
                advertised.update(FLEX_ITEM_PROPS)
            assert {r.feature_name for r in shared if r.feature_kind == "property"} == advertised
            assert all(r.scenario_id in ("default", "valid_boundary", "invalid_rejection")
                       for r in shared if r.feature_kind == "property")
        for backend in BACKENDS:
            family = "qt" if backend.startswith(("pyqt", "pyside")) else (
                "tk" if backend == "tkinter" else backend)
            subset = [r for r in records if r.backend == backend and r.component == component]
            assert subset
            partial_grid = backend in ("headless", "pyside6", "pyside2", "pyqt5", "pyqt6", "tkinter", "kivy") and component in ("Grid", "GridItem")
            assert all(r.applicability == native[(family, component)] or (
                partial_grid and r.applicability == "partial_native"
            ) for r in subset)
            assert not any(r.scenario_id in ("default", "valid_boundary", "invalid_rejection")
                           for r in subset)
            if native[(family, component)] == "unported":
                classification = [r for r in subset if r.applicability == "unported"]
                assert len(classification) == 1
                assert classification[0].scenario_id == "classification_review"
                if not partial_grid:
                    assert len(subset) == 1


def test_unexecuted_behavior_remains_pending():
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    result = validate_receipts((row,), [], sha=SHA)
    assert result["pending"] == 1 and not result["complete"]


def _receipt(row, path, *, status="executed_pass"):
    return {**asdict(row), "status": status, "sha": SHA,
            "test_id": "tests.test_sample::test_behavior",
            "environment": "linux-python-3.12",
            "junit_artifact": str(path)}


def _junit(path, row, *, state=None, asserted=True, duplicate=False):
    root = ET.Element("testsuite")
    case = ET.SubElement(root, "testcase", classname="tests.test_sample",
                         name="test_behavior")
    props = ET.SubElement(case, "properties")
    if asserted:
        for _ in range(2 if duplicate else 1):
            ET.SubElement(props, "property", name=RECEIPT_PROPERTY,
                          value=json.dumps(dict(zip((
                              "component", "backend", "feature_kind",
                              "feature_name", "scenario_id"), feature_key(row)))))
    if state:
        ET.SubElement(case, state)
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_real_assertion_receipt_proves_exact_feature(tmp_path):
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    path = tmp_path / "executed.xml"
    _junit(path, row)
    result = validate_receipts((row,), [_receipt(row, path)], sha=SHA)
    assert result["complete"] and result["executed_pass"] == 1


@pytest.mark.parametrize("state", ["failure", "error", "skipped", None])
def test_invalid_or_unmarked_junit_cannot_certify(state, tmp_path):
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    path = tmp_path / "invalid.xml"
    _junit(path, row, state=state, asserted=bool(state))
    with pytest.raises(ValueError, match="Missing successful feature assertion"):
        validate_receipts((row,), [_receipt(row, path)], sha=SHA)


def test_duplicate_assertion_rejected(tmp_path):
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    path = tmp_path / "dupe.xml"
    _junit(path, row, duplicate=True)
    with pytest.raises(ValueError, match="Duplicate feature"):
        validate_receipts((row,), [_receipt(row, path)], sha=SHA)


def test_unknown_duplicate_and_foreign_sha_fail(tmp_path):
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    path = tmp_path / "executed.xml"
    _junit(path, row)
    receipt = _receipt(row, path)
    for bad in ([receipt, receipt], [{**receipt, "component": "Text"}],
                [{**receipt, "sha": "b" * 40}]):
        with pytest.raises(ValueError):
            validate_receipts((row,), bad, sha=SHA)


def test_unported_exclusion_requires_assertion_and_reviewer(tmp_path):
    row = Feature("Input", "headless", "capability", "native_host",
                  "classification_review", applicability="unported")
    path = tmp_path / "negative.xml"
    _junit(path, row)
    exclusion = {**_receipt(row, path, status="unsupported"),
                 "reason": "No native geometry port"}
    with pytest.raises(ValueError, match="Unreviewed"):
        validate_receipts((row,), [exclusion], sha=SHA)
    exclusion["reviewed_by"] = "independent-review"
    assert validate_receipts((row,), [exclusion], sha=SHA)["excluded"] == 1
    with pytest.raises(ValueError, match="Unported"):
        validate_receipts((row,), [_receipt(row, path)], sha=SHA)


def test_native_positive_cannot_be_arbitrarily_excluded():
    row = Feature("Button", "pyside6", "event", "on_click", "payload",
                  applicability="native")
    receipt = {**asdict(row), "status": "not_applicable",
               "reason": "Convenience", "reviewed_by": "test"}
    with pytest.raises(ValueError, match="Required native behavior"):
        validate_receipts((row,), [receipt], sha=SHA)


def test_assert_feature_records_only_after_successful_assertion():
    class Node:
        user_properties = []
    class Request:
        node = Node()
    row = Feature("Button", CONTRACT, "property", "enabled", "default")
    with pytest.raises(AssertionError):
        assert_feature(Request(), row, False)
    assert not Request.node.user_properties
    assert_feature(Request(), row, True)
    assert Request.node.user_properties[0][0] == RECEIPT_PROPERTY


def test_collector_imports_only_assertion_bound_success(tmp_path):
    from tests.certification.public_behavior_census import collect_executed_receipts
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    artifact = tmp_path / "native.xml"
    _junit(artifact, row)
    claims = collect_executed_receipts((row,), (artifact,), sha=SHA,
                                       environment="linux-pyside6")
    assert len(claims) == 1
    assert validate_receipts((row,), claims, sha=SHA)["complete"]
    _junit(artifact, row, state="failure")
    failed = collect_executed_receipts((row,), (artifact,), sha=SHA,
                                       environment="linux-pyside6")
    assert failed[0]["status"] == "failed"
    assert not validate_receipts((row,), failed, sha=SHA)["complete"]


def test_collector_does_not_assign_unmarked_general_tests(tmp_path):
    from tests.certification.public_behavior_census import collect_executed_receipts
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    artifact = tmp_path / "unmarked.xml"
    _junit(artifact, row, asserted=False)
    assert collect_executed_receipts((row,), (artifact,), sha=SHA,
                                    environment="linux-pyside6") == []


def test_collector_rejects_foreign_or_double_claims(tmp_path):
    from tests.certification.public_behavior_census import collect_executed_receipts
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    artifact = tmp_path / "invalid.xml"
    _junit(artifact, row, duplicate=True)
    with pytest.raises(ValueError, match="Duplicate assertions"):
        collect_executed_receipts((row,), (artifact,), sha=SHA,
                                  environment="linux")
    _junit(artifact, row)
    with pytest.raises(ValueError, match="Unknown source feature"):
        collect_executed_receipts((), (artifact,), sha=SHA, environment="linux")


def test_shared_validation_is_not_multiplied_by_binding_count():
    rows = inventory()
    native = [row for row in rows if row.backend != CONTRACT]
    shared = [row for row in rows if row.backend == CONTRACT]
    assert shared and native
    # Only native interactions/events require independent toolkit evidence.
    for row in native:
        assert not (row.feature_kind == "property" and row.feature_name.startswith("on_"))
    from tests.certification.public_behavior_census import INTERACTIONS
    for component, pairs in INTERACTIONS.items():
        for a, b in pairs:
            expected = f"{a}__{b}"
            assert any(row.component == component and row.feature_kind == "interaction"
                       and row.feature_name == expected for row in native)


def test_unsupported_does_not_expand_to_fake_property_coverage():
    rows = inventory()
    headless = [row for row in rows if row.component == "Input"
                and row.backend == "headless"]
    assert len(headless) == 1
    assert headless[0].applicability == "unported"
    assert headless[0].scenario_id == "classification_review"


def test_final_aggregator_rechecks_original_junit_and_sha(tmp_path):
    from tests.certification.public_behavior_census import merge_executed_manifests
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    junit = tmp_path / "native.xml"
    _junit(junit, row)
    receipt = _receipt(row, junit)
    receipt["junit_artifact"] = junit.name
    manifest = tmp_path / "receipts.json"
    manifest.write_text(json.dumps({
        "summary": {"sha": SHA}, "receipts": [receipt],
    }), encoding="utf-8")
    report = merge_executed_manifests((row,), (manifest,), sha=SHA,
                                       require_complete=True)
    assert report["complete"] and report["executed_pass"] == 1
    with pytest.raises(ValueError, match="Foreign-SHA"):
        merge_executed_manifests((row,), (manifest,), sha="b" * 40)
    _junit(junit, row, state="skipped")
    with pytest.raises(ValueError, match="Missing successful"):
        merge_executed_manifests((row,), (manifest,), sha=SHA)


def test_final_aggregator_rejects_missing_coverage_and_duplicate_manifests(tmp_path):
    from tests.certification.public_behavior_census import merge_executed_manifests
    row = Feature("Button", "pyside6", "event", "on_click", "native_dispatch")
    other = Feature("Button", "pyside6", "event", "on_click", "payload")
    junit = tmp_path / "native.xml"
    _junit(junit, row)
    manifest = tmp_path / "receipts.json"
    receipt = _receipt(row, junit)
    receipt["junit_artifact"] = junit.name
    manifest.write_text(json.dumps({"summary": {"sha": SHA},
                                    "receipts": [receipt]}), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        merge_executed_manifests((row, other), (manifest,),
                                 sha=SHA, require_complete=True)
    with pytest.raises(ValueError, match="duplicate"):
        merge_executed_manifests((row,), (manifest, manifest), sha=SHA)


def test_scoped_contract_certificate_fails_closed_without_every_applicable_case(tmp_path):
    """A scoped release may leave unrelated backlog pending, never its own cells."""
    from tests.certification.public_behavior_census import merge_executed_manifests
    covered = Feature("Grid", CONTRACT, "public_api", "declaration", "builder",
                      applicability="shared")
    missing = Feature("Grid", CONTRACT, "public_api", "declaration", "markup",
                      applicability="shared")
    other = Feature("Text", CONTRACT, "property", "value", "default",
                    applicability="shared")
    junit = tmp_path / "core.xml"
    _junit(junit, covered)
    receipt = _receipt(covered, junit)
    receipt["junit_artifact"] = junit.name
    manifest = tmp_path / "core-receipts.json"
    manifest.write_text(json.dumps({"summary": {"sha": SHA}, "receipts": [receipt]}),
                        encoding="utf-8")
    with pytest.raises(ValueError, match="Incomplete component contract"):
        merge_executed_manifests((covered, missing, other), (manifest,), sha=SHA,
                                 require_contract_components=("Grid",))
    scoped = merge_executed_manifests((covered, other), (manifest,), sha=SHA,
                                      require_contract_components=("Grid",))
    assert scoped["contract_scope"]["complete"]
    assert scoped["contract_scope"]["required"] == 1
    assert not scoped["complete"]  # Unrelated missing evidence remains visible.
    with pytest.raises(ValueError, match="Unknown contract certification"):
        merge_executed_manifests((covered, other), (manifest,), sha=SHA,
                                 require_contract_components=("GridItem",))


def test_grid_native_certificate_requires_executed_backend_receipts(tmp_path):
    from tests.certification.public_behavior_census import merge_executed_manifests
    grid_rows = tuple(row for row in inventory()
                      if row.component in ("Grid", "GridItem")
                      and row.applicability == "partial_native")
    assert {row.backend for row in grid_rows} == {
        "headless", "pyside6", "pyside2", "pyqt5", "pyqt6", "tkinter", "kivy"
    }
    assert len(grid_rows) == 129
    manifest = tmp_path / "no-native-receipts.json"
    manifest.write_text(json.dumps({"summary": {"sha": SHA}, "receipts": []}))
    with pytest.raises(ValueError, match="Incomplete native Grid certification"):
        merge_executed_manifests(
            tuple(inventory()), (manifest,), sha=SHA,
            require_native_components=("Grid", "GridItem"))
