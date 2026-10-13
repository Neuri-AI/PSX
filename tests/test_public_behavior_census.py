"""Source-derived behavior census and fail-closed receipt tests."""
from __future__ import annotations

from dataclasses import asdict

import pytest

from tests.certification.public_behavior_census import (
    BACKENDS, Feature, inventory, validate_receipts,
)

SHA = "a" * 40


def test_registry_contract_census_includes_all_live_components():
    from psx.core.registry import builtin_component_registry

    definitions = builtin_component_registry().snapshot()
    records = inventory()
    assert {row.component for row in records} == set(definitions)
    assert {row.backend for row in records} == set(BACKENDS)
    assert all(row.status == "pending" for row in records)
    assert len(records) == len(set(records))
    for name, definition in definitions.items():
        subset = [row for row in records if row.component == name]
        assert subset
        if definition.contract is not None:
            assert {
                row.feature_name for row in subset if row.feature_kind == "property"
            } >= set(definition.contract.properties)
            assert {
                row.feature_name for row in subset if row.feature_kind == "event"
            } == set(definition.contract.events)


def test_unverified_behavior_must_remain_pending():
    rows = (Feature("Button", "pyside6", "event", "on_click", "native_dispatch"),)
    report = validate_receipts(rows, [], sha=SHA)
    assert report["pending"] == 1
    assert report["complete"] is False


@pytest.mark.parametrize("status", ["executed_pass", "skipped", "passed", "unknown"])
def test_fabricated_or_nonexecuted_status_rejected(status, tmp_path):
    rows = (Feature("Button", "pyside6", "event", "on_click", "native_dispatch"),)
    data = {**asdict(rows[0]), "status": status}
    if status == "executed_pass":
        data.update(sha=SHA, test_id="fake::test_click", environment="ubuntu",
                    junit_artifact=str(tmp_path / "missing.xml"))
    with pytest.raises(ValueError):
        validate_receipts(rows, [data], sha=SHA)


def test_reject_foreign_component_and_duplicate_row():
    rows = (Feature("Button", "pyside6", "event", "on_click", "native_dispatch"),)
    receipt = {**asdict(rows[0]), "status": "pending"}
    with pytest.raises(ValueError):
        validate_receipts(rows, [receipt, receipt], sha=SHA)
    with pytest.raises(ValueError):
        validate_receipts(rows, [{**receipt, "component": "Text"}], sha=SHA)


def test_exclusion_requires_reason():
    rows = (Feature("Input", "kivy", "lifecycle", "mount", "native_behavior"),)
    with pytest.raises(ValueError):
        validate_receipts(rows, [{**asdict(rows[0]), "status": "unsupported"}], sha=SHA)


def test_matching_executed_junit_test_is_accepted(tmp_path):
    rows = (Feature("Button", "pyside6", "event", "on_click", "native_dispatch"),)
    artifact = tmp_path / "native.xml"
    artifact.write_text(
        '<testsuite><testcase classname="tests.test_button" name="test_native_click"/></testsuite>',
        encoding="utf-8",
    )
    receipt = {**asdict(rows[0]), "status": "executed_pass",
               "sha": SHA, "environment": "linux pyside6",
               "test_id": "tests.test_button::test_native_click",
               "junit_artifact": str(artifact)}
    result = validate_receipts(rows, [receipt], sha=SHA)
    assert result["complete"] and result["executed_pass"] == 1
    artifact.write_text(
        '<testsuite><testcase classname="tests.test_button" name="test_native_click">'
        '<skipped/></testcase></testsuite>', encoding="utf-8",
    )
    with pytest.raises(ValueError):
        validate_receipts(rows, [receipt], sha=SHA)


def test_backend_applicability_is_source_derived_and_no_unsupported_passes():
    from tests.certification.native_component_matrix import native_certification_matrix

    source = {(cell.backend, cell.component): cell.status
              for cell in native_certification_matrix()}
    expected = {"pyside6": "qt", "pyqt6": "qt", "pyqt5": "qt",
                "pyside2": "qt", "kivy": "kivy",
                "tkinter": "tk", "headless": "headless"}
    for row in inventory():
        assert row.applicability == source[(expected[row.backend], row.component)]
        assert row.status == "pending"
    assert any(row.component == "Input" and row.backend == "headless"
               and row.applicability == "unported" for row in inventory())
    assert any(row.component == "Button" and row.backend == "pyside6"
               and row.applicability == "native" for row in inventory())


def test_unported_backend_cannot_imitate_executed_native_pass(tmp_path):
    row = Feature("Input", "headless", "event", "on_change",
                  "native_dispatch", applicability="unported")
    source = tmp_path / "receipt.xml"
    source.write_text('<testsuite><testcase classname="tests.input" name="test_input"/></testsuite>')
    claim = {**asdict(row), "status": "executed_pass", "sha": SHA,
             "test_id": "tests.input::test_input", "environment": "headless",
             "junit_artifact": str(source)}
    with pytest.raises(ValueError, match="Unsupported native backend"):
        validate_receipts((row,), [claim], sha=SHA)


def test_claimed_unsupported_requires_genuine_negative_junit(tmp_path):
    row = Feature("Input", "headless", "event", "on_change",
                  "native_dispatch", applicability="unported")
    receipt = {**asdict(row), "status": "unsupported",
               "reason": "No admitted native SFLE geometry port",
               "sha": SHA, "test_id": "tests.input::test_rejected",
               "environment": "headless",
               "junit_artifact": str(tmp_path / "missing.xml")}
    with pytest.raises(ValueError, match="Missing JUnit"):
        validate_receipts((row,), [receipt], sha=SHA)
    path = tmp_path / "missing.xml"
    path.write_text('<testsuite><testcase classname="tests.input" name="test_rejected"/></testsuite>')
    assert validate_receipts((row,), [receipt], sha=SHA)["excluded"] == 1
    with pytest.raises(ValueError, match="Supported native capability"):
        validate_receipts((
            Feature("Input", "pyside6", "event", "on_change",
                    "native_dispatch", applicability="native"),
        ), [{**receipt, "backend": "pyside6"}], sha=SHA)


def test_not_applicable_requires_explicit_reviewer():
    row = Feature("Native", "headless", "lifecycle", "unmount",
                  "native_behavior", applicability="external_port_required")
    receipt = {**asdict(row), "status": "not_applicable",
               "reason": "No external native host in Headless"}
    with pytest.raises(ValueError, match="Unreviewed"):
        validate_receipts((row,), [receipt], sha=SHA)
    receipt["reviewed_by"] = "independent-review-fixture"
    assert validate_receipts((row,), [receipt], sha=SHA)["excluded"] == 1
