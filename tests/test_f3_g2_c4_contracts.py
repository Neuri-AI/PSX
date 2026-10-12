"""C4 ownership manifest must reject gaps, skips and fabricated receipts."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from psx.sfle.f3_g2_c4 import C4_BY_BACKEND, C4_CASES
from psx.sfle.f3_g2_c4_receipts import certify_c4


def test_c4_inventory_has_explicit_external_variants_for_each_backend():
    assert set(C4_BY_BACKEND) == {"qt", "tk", "kivy"}
    required = {"native_owned", "native_borrowed", "custom_adapter"}
    for backend, cases in C4_BY_BACKEND.items():
        assert {item.variant for item in cases} == required
        assert all(item.test_name.startswith("test_") for item in cases)
        assert all(item.expectation for item in cases)
        assert len({item.variant for item in cases}) == len(cases)
    assert {case.expectation for case in C4_CASES if
            case.backend == "tk" and case.variant == "native_borrowed"} == {
                "rejected_without_mutation"
            }


def test_c4_execution_receipt_requires_passed_non_skipped_tests(tmp_path):
    backend = "qt"
    cases = C4_BY_BACKEND[backend]
    root = ET.Element("testsuite")
    for test in {c.test_name for c in cases}:
        ET.SubElement(root, "testcase", name=test)
    path = tmp_path / "c4.xml"
    ET.ElementTree(root).write(path)
    result = certify_c4(backend, path)
    assert len(result["cases"]) == len(cases)
    assert all(c["status"] == "executed_pass" for c in result["cases"])

    missing = ET.Element("testsuite")
    ET.SubElement(missing, "testcase", name="an_unrelated_test")
    ET.ElementTree(missing).write(path)
    with pytest.raises(ValueError, match="Missing/failed"):
        certify_c4(backend, path)

    skipped = ET.Element("testsuite")
    for test in {c.test_name for c in cases}:
        case = ET.SubElement(skipped, "testcase", name=test)
        ET.SubElement(case, "skipped")
    ET.ElementTree(skipped).write(path)
    with pytest.raises(ValueError, match="Missing/failed"):
        certify_c4(backend, path)

    ET.ElementTree(root).write(path)
    ET.SubElement(root, "testcase", name=cases[0].test_name)
    ET.SubElement(root[-1], "failure")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="Missing/failed"):
        certify_c4(backend, path)


def test_c4_receipts_reject_unknown_backend(tmp_path):
    with pytest.raises(ValueError, match="Unknown C4 backend"):
        certify_c4("headless", tmp_path / "missing.xml")
