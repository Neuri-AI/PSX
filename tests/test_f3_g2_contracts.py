"""C2 contract audit: classification, executable mechanisms, and receipts.

This suite intentionally does not turn a source reference into a runtime PASS:
C3–C5 must provide real semantic assertions for every pending contract.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from psx.sfle.f3_g2_contracts import (
    OWNER_BLOCK, g2_contract_summary, g2_operation_contracts,
)
from psx.sfle.f3_g2_evidence import COMPONENT_OPERATION_TESTS
from psx.sfle.f3_g2_matrix import BACKENDS, OPERATIONS, g2_certification_matrix
from psx.sfle.f3_g2_receipts import certify_junit
from psx.sfle.f3_g2_oracles import ORACLES, Observation


def test_every_registry_backend_operation_has_a_unique_runnable_contract():
    contracts = g2_operation_contracts()
    native_cells = g2_certification_matrix()
    assert len(contracts) == len(native_cells) * len(OPERATIONS)
    assert len({contract.key for contract in contracts}) == len(contracts)
    assert {c.backend for c in contracts} == set(BACKENDS)
    for contract in contracts:
        assert contract.operation in OPERATIONS
        assert contract.applicability in {"required", "not_applicable"}
        assert contract.mechanism in {"pytest_reference", "oracle_pending_driver", "exclusion"}
        assert contract.reason
        if contract.applicability == "not_applicable":
            assert contract.mechanism == "exclusion"
            assert contract.reference is None
            assert contract.oracle is None
        elif contract.mechanism == "pytest_reference":
            assert contract.reference == COMPONENT_OPERATION_TESTS[contract.key]
        else:
            assert contract.mechanism == "oracle_pending_driver"
            assert contract.reference is None
            assert OWNER_BLOCK[contract.operation] in contract.reason
        if contract.applicability == "required":
            assert contract.oracle == contract.operation
            assert callable(ORACLES[contract.oracle])
    counts = g2_contract_summary()
    for backend in BACKENDS:
        assert sum(counts[backend].values()) == (
            len([c for c in native_cells if c.backend == backend])
            * len(OPERATIONS)
        )


def _xml(tmp_path: Path, cases: tuple[tuple[str, str], ...]) -> Path:
    root = ET.Element("testsuite")
    for name, state in cases:
        case = ET.SubElement(root, "testcase", name=name)
        if state != "pass":
            ET.SubElement(case, state)
    result = tmp_path / "results.xml"
    ET.ElementTree(root).write(result, encoding="utf-8")
    return result


def test_receipt_fails_if_a_claimed_test_never_ran(tmp_path):
    source = _xml(tmp_path, (("unrelated_test", "pass"),))
    with pytest.raises(ValueError, match="Missing or failing"):
        certify_junit("qt", source)


@pytest.mark.parametrize("outcome", ("failure", "error", "skipped"))
def test_receipt_fails_when_claimed_test_did_not_pass(tmp_path, outcome):
    references = sorted({
        c.reference for c in g2_operation_contracts()
        if c.backend == "headless" and c.reference
    })
    rows = tuple((name, outcome if index == 0 else "pass")
                 for index, name in enumerate(references))
    with pytest.raises(ValueError, match="Missing or failing"):
        certify_junit("headless", _xml(tmp_path, rows))


def test_receipt_reports_execution_and_pendings_separately(tmp_path):
    references = sorted({
        c.reference for c in g2_operation_contracts()
        if c.backend == "headless" and c.reference
    })
    source = _xml(tmp_path, tuple((name, "pass") for name in references))
    report = certify_junit("headless", source)
    assert any(c["status"] == "executed_pass" for c in report["contracts"])
    assert any(c["status"] == "pending" for c in report["contracts"])
    assert any(c["status"] == "not_applicable" for c in report["contracts"])
    assert all(c["status"] != "invalid_reference" for c in report["contracts"])
    assert not any(c["status"] == "executed_pass" and not c["reference"]
                   for c in report["contracts"])


def test_parametrized_receipt_needs_all_parameter_cases_green(tmp_path):
    references = sorted({
        c.reference for c in g2_operation_contracts()
        if c.backend == "headless" and c.reference
    })
    rows = [(name, "pass") for name in references]
    rows.append((references[0] + "[variant]", "failure"))
    with pytest.raises(ValueError, match="Missing or failing"):
        certify_junit("headless", _xml(tmp_path, tuple(rows)))


@pytest.mark.parametrize("operation", ("create", "update", "reorder", "unmount",
                                      "event_rebind", "borrowed_ownership",
                                      "rollback", "invalidation"))
def test_every_operation_oracle_has_positive_and_negative_behavior(operation):
    old = Observation(
        native_identity="native-1", mounted=True, rect=(0, 0, 20, 10),
        state="before", order=("a", "b"), events=(),
        callback_identity="old", owner="psx", revision=1,
        remeasure_count=1,
    )
    borrowed = Observation(**{**vars_for(old), "owner": "caller"})
    changed = {
        "create": (None, old),
        "update": (old, Observation(**{**vars_for(old), "state": "after"})),
        "reorder": (old, Observation(**{**vars_for(old), "order": ("b", "a")})),
        "unmount": (old, Observation(**{**vars_for(old), "mounted": False, "disposed": True})),
        "event_rebind": (old, Observation(**{
            **vars_for(old), "callback_identity": "new", "events": ("new",),
        })),
        "borrowed_ownership": (borrowed, borrowed),
        "rollback": (old, Observation(**{**vars_for(old), "mutation_failed": True})),
        "invalidation": (old, Observation(**{
            **vars_for(old), "revision": 2, "remeasure_count": 2,
        })),
    }
    before, after = changed[operation]
    ORACLES[operation](before, after)
    with pytest.raises(AssertionError):
        ORACLES[operation](old, Observation(**{
            **vars_for(old), "native_identity": None,
            "owner": "psx", "rect": None, "mounted": False,
        }))


def vars_for(observation):
    from dataclasses import asdict
    return asdict(observation)


def test_all_required_builtin_lifecycle_operations_have_component_drivers():
    """Fail closed before C4 if any native component lacks a C3 driver."""
    required = {"create", "update", "reorder", "unmount", "event_rebind", "rollback"}
    open_contracts = [
        (c.backend, c.component, c.operation)
        for c in g2_operation_contracts()
        if c.operation in required and c.applicability == "required"
        and (c.mechanism != "pytest_reference" or not c.reference)
    ]
    assert not open_contracts, (
        "C3 lifecycle operations without executable component-specific "
        f"evidence: {open_contracts}"
    )
    for backend in BACKENDS:
        assert any(c.backend == backend and c.operation == "rollback"
                   and c.mechanism == "pytest_reference"
                   for c in g2_operation_contracts())
