"""C6 certifier negative fixtures and forward-compatible component-family policy."""
from __future__ import annotations
import xml.etree.ElementTree as ET
import pytest
from tests.certification.f3_g2_c6_receipts import certify_c6
from tests.certification.f3_g2_contracts import g2_operation_contracts

@pytest.mark.parametrize("backend", ("qt", "tk", "kivy", "headless"))
def test_c6_certification_is_complete_and_rejects_invalid_junit(backend, tmp_path):
    required = [c for c in g2_operation_contracts()
                if c.backend == backend and c.applicability == "required"]
    assert required
    assert all(c.reference for c in required), [
        c.key for c in required if not c.reference
    ]
    root = ET.Element("testsuite")
    for method in sorted({c.reference for c in required}):
        ET.SubElement(root, "testcase", name=method)
    path = tmp_path / "cases.xml"
    ET.ElementTree(root).write(path)
    report = certify_c6(backend, path)
    assert report["pending"] == 0
    assert report["executed_pass"] == len(required)
    assert len(report["contracts"]) == len([
        c for c in g2_operation_contracts() if c.backend == backend
    ])
    first = root[0]
    root.remove(first)
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="missing/failed"):
        certify_c6(backend, path)
    root.insert(0, first)
    ET.SubElement(first, "skipped")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="missing/failed"):
        certify_c6(backend, path)
    first.remove(first.find("skipped"))
    ET.SubElement(first, "failure")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="missing/failed"):
        certify_c6(backend, path)

def test_c6_unknown_backend_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="Unknown C6 backend"):
        certify_c6("unregistered", tmp_path / "not-created.xml")
