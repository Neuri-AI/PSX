"""The C5 certificate must reject missing, skipped and failing JUnit evidence."""
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, ElementTree

import pytest

from tests.certification.native_invalidation_receipts import (
    COMPONENT_DRIVERS, REASON_DRIVERS, ADDITIONAL_DRIVERS, certify_c5,
)


@pytest.mark.parametrize("backend", tuple(COMPONENT_DRIVERS))
def test_c5_receipt_matrix_requires_every_real_native_driver(backend, tmp_path):
    expected = sorted({COMPONENT_DRIVERS[backend], REASON_DRIVERS[backend],
                       *ADDITIONAL_DRIVERS[backend]})
    xml = tmp_path / "junit.xml"
    root = Element("testsuite")
    for name in expected:
        SubElement(root, "testcase", {"name": name, "classname": "native"})
    ElementTree(root).write(xml)
    result = certify_c5(backend, xml)
    assert result["pending"] == 0
    assert result["executed_pass"] == result["required_cases"]
    assert result["required_cases"] == result["component_count"] * 6
    assert {x["component"] for x in result["contracts"]}
    assert {x["reason"] for x in result["contracts"]} == {
        "content", "font", "theme", "resource", "dpi", "viewport",
    }

    # A success for one component/backend is not transferable to another,
    # nor is a skipped native race proof a successful receipt.
    missing = expected[0]
    case = next(c for c in root.findall("testcase") if c.get("name") == missing)
    root.remove(case)
    ElementTree(root).write(xml)
    with pytest.raises(ValueError, match="receipts absent or failing"):
        certify_c5(backend, xml)
    root.append(case)
    SubElement(case, "skipped")
    ElementTree(root).write(xml)
    with pytest.raises(ValueError, match="receipts absent or failing"):
        certify_c5(backend, xml)
    case.remove(case.find("skipped"))
    SubElement(case, "failure")
    ElementTree(root).write(xml)
    with pytest.raises(ValueError, match="receipts absent or failing"):
        certify_c5(backend, xml)
