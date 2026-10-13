"""Fail-closed Scroll-only JUnit evidence validation."""
import xml.etree.ElementTree as ET

import pytest

from tests.certification.scroll_operation_receipts import (
    REQUIRED, TEST_MODULE, certify_scroll_receipts,
)


def write_cases(path, backend, *, missing=None, invalid=None,
                foreign=None, name_override=None):
    root = ET.Element("testsuite")
    for operation, name in REQUIRED[backend].items():
        if operation == missing:
            continue
        case = ET.SubElement(
            root, "testcase",
            classname=foreign or TEST_MODULE[backend] + ".NativeScrollTests",
            name=(name_override or name) if operation == invalid else name,
        )
        if operation == invalid and not name_override:
            ET.SubElement(case, "skipped")
    ET.ElementTree(root).write(path, encoding="utf-8")


@pytest.mark.parametrize("backend", tuple(REQUIRED))
def test_scroll_certifier_accepts_complete_backend_specific_receipts(backend, tmp_path):
    source = tmp_path / "executed.xml"
    write_cases(source, backend)
    result = certify_scroll_receipts(backend, source)
    assert result["executed_pass"] == len(REQUIRED[backend])
    assert all(row["status"] in ("executed_pass", "not_applicable")
               for row in result["records"])


@pytest.mark.parametrize("backend", tuple(REQUIRED))
def test_scroll_certifier_rejects_missing_required_operation(backend, tmp_path):
    source = tmp_path / "missing.xml"
    write_cases(source, backend, missing=next(iter(REQUIRED[backend])))
    with pytest.raises(ValueError, match="Missing/failing"):
        certify_scroll_receipts(backend, source)


@pytest.mark.parametrize("backend", tuple(REQUIRED))
def test_scroll_certifier_rejects_skipped_required_operation(backend, tmp_path):
    source = tmp_path / "skipped.xml"
    write_cases(source, backend, invalid=next(iter(REQUIRED[backend])))
    with pytest.raises(ValueError, match="Missing/failing"):
        certify_scroll_receipts(backend, source)


@pytest.mark.parametrize("backend", tuple(REQUIRED))
def test_scroll_certifier_rejects_evidence_from_another_suite(backend, tmp_path):
    source = tmp_path / "foreign.xml"
    write_cases(source, backend, foreign="tests.test_unrelated_layout")
    with pytest.raises(ValueError, match="Missing/failing"):
        certify_scroll_receipts(backend, source)


def test_scroll_certifier_rejects_unknown_backend(tmp_path):
    with pytest.raises(ValueError, match="Unknown Scroll"):
        certify_scroll_receipts("unknown", tmp_path / "not-created.xml")


def test_scroll_certifier_rejects_mixed_pass_and_fail_for_same_test(tmp_path):
    source = tmp_path / "mixed.xml"
    write_cases(source, "qt")
    root = ET.parse(source).getroot()
    name = next(iter(REQUIRED["qt"].values()))
    case = ET.SubElement(root, "testcase",
                         classname=TEST_MODULE["qt"] + ".NativeScrollTests", name=name)
    ET.SubElement(case, "failure", message="genuine assertion failed")
    ET.ElementTree(root).write(source)
    with pytest.raises(ValueError, match="Missing/failing"):
        certify_scroll_receipts("qt", source)
