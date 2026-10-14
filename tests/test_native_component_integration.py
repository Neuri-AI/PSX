"""C6 iteration 2: fail-closed registry and native integration census.

This checks the *complete* classified registry, per-component native-driver
evidence and external-owned/borrowed/custom port obligations. Native behavior
is executed by backend jobs; source references alone are never PASS receipts.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from psx.core.registry import builtin_component_registry
from psx.sfle.native_component_matrix import (
    BACKENDS, HEADLESS_PORTED, LEGACY, EXTERNAL, STRUCTURAL, TRANSPARENT,
    native_certification_matrix,
)
from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
from tests.certification.native_external_ownership_cases import EXTERNAL_OWNERSHIP_CASES_BY_BACKEND
from tests.certification.native_operation_evidence import COMPONENT_OPERATION_TESTS, SUITES

NATIVE_DRIVER = {
    "qt": "test_registered_builtin_lifecycle_keeps_real_native_identity",
    "tk": "test_registered_builtin_lifecycle_keeps_real_native_identity",
    "kivy": "test_all_ported_builtin_lifecycles_keep_native_widget_handles",
    "headless": "test_all_supported_headless_components_reconcile_without_remount",
}
PORT_CASES = {"native_owned", "native_borrowed", "custom_adapter"}
ROOT = Path(__file__).resolve().parent


def test_native_acceptance_all_registry_backend_pairs_are_classified_without_phantom_ports():
    names = set(builtin_component_registry().snapshot())
    matrix = native_certification_matrix()
    assert len(matrix) == len(names) * len(BACKENDS)
    assert {(cell.backend, cell.component) for cell in matrix} == {
        (backend, name) for backend in BACKENDS for name in names
    }
    assert names >= LEGACY | EXTERNAL | STRUCTURAL | TRANSPARENT
    for backend in BACKENDS:
        native = set(NATIVE_LEAF_TYPES[backend]) | STRUCTURAL if backend != "headless" else HEADLESS_PORTED
        cells = [cell for cell in matrix if cell.backend == backend]
        assert {cell.component for cell in cells if cell.status == "native"} == native
        for cell in cells:
            if cell.component in LEGACY:
                assert cell.status == "legacy_deferred"
            elif cell.component in TRANSPARENT:
                assert cell.status == "transparent"
            elif cell.component in EXTERNAL:
                assert cell.status == "external_port_required"
            elif cell.status == "unported":
                assert backend == "headless" or cell.component in {"Grid", "GridItem"}, (backend, cell.component)
                assert cell.component not in native
            else:
                assert cell.status == "native"


@pytest.mark.parametrize("backend", BACKENDS)
def test_native_acceptance_every_supported_native_component_has_real_geometry_driver(backend):
    source = (ROOT / SUITES[backend]).read_text(encoding="utf-8")
    module = ast.parse(source)
    candidates = [node for node in ast.walk(module) if
                  isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name == NATIVE_DRIVER[backend]]
    assert len(candidates) == 1
    method = ast.get_source_segment(source, candidates[0])
    assert method
    assert "NATIVE_LEAF_TYPES" in method or "HEADLESS_PORTED" in method
    assert "set(factories)" in method
    assert "request_sfle_invalidation" in method
    # It must check more than mount/unmount or literal component names:
    # positive native rectangles and preserved handles are mandatory.
    assert ("native_widget" in method or "widget" in method or "handle" in method)
    assert ("geometry" in method or "rect(" in method or ".width" in method)
    native = {cell.component for cell in native_certification_matrix()
              if cell.backend == backend and cell.status == "native"}
    for component in native:
        assert component in method, (backend, component)


@pytest.mark.parametrize("backend", ("qt", "tk", "kivy"))
def test_native_acceptance_external_native_ports_have_explicit_owned_borrowed_custom_contract(backend):
    cases = EXTERNAL_OWNERSHIP_CASES_BY_BACKEND[backend]
    assert PORT_CASES <= {case.variant for case in cases}
    assert len(cases) == len({case.variant for case in cases})
    for case in cases:
        assert case.backend == backend
        assert case.expectation
        assert case.test_name.startswith("test_")
    borrowed = next(case for case in cases if case.variant == "native_borrowed")
    if backend == "tk":
        assert borrowed.expectation == "rejected_without_mutation"
    else:
        assert borrowed.expectation == "retained_and_reparented"


@pytest.mark.parametrize("backend", ("qt", "tk", "kivy"))
def test_native_acceptance_native_leaf_and_custom_adapter_geometry_do_not_inherit_evidence(backend):
    native = {c.component for c in native_certification_matrix()
              if c.backend == backend and c.status == "native"}
    assert all((backend, component, "create") in COMPONENT_OPERATION_TESTS
               for component in native)
    assert not any((backend, "Native", operation) in COMPONENT_OPERATION_TESTS
                   for operation in ("create", "invalidation"))
    assert "custom_adapter" in {case.variant for case in EXTERNAL_OWNERSHIP_CASES_BY_BACKEND[backend]}
