"""Non-silent G2 registry/backend/operation coverage audit.

These tests are a census, not a claim that the G2 gate is closed.
"""
import ast
from pathlib import Path

import pytest

from psx.core.registry import builtin_component_registry
from psx.sfle.f3_native_coverage import G2_LEAF_TYPES
from psx.sfle.f3_g2_evidence import COMPONENT_OPERATION_TESTS, SUITES as COMPONENT_SUITES
from psx.sfle.f3_g2_matrix import (
    BACKENDS, EVIDENCE, OPERATIONS, g2_certification_matrix, g2_matrix_summary,
)

SUITES = {
    "qt": "test_f3_g2_qt_family.py",
    "tk": "test_tkinter_f3_g2_renderer.py",
    "kivy": "test_kivy_f3_g2_renderer.py",
    "headless": "test_f3_g2_headless.py",
}


def test_every_registered_component_backend_cell_is_explicit_and_unique():
    actual = {(c.backend, c.component) for c in g2_certification_matrix()}
    expected = {
        (backend, name)
        for backend in BACKENDS
        for name in builtin_component_registry().snapshot()
    }
    assert actual == expected
    assert len(g2_certification_matrix()) == len(expected)


@pytest.mark.parametrize("backend", BACKENDS)
def test_declared_native_ports_match_the_actual_registry(backend):
    registered = set(builtin_component_registry().snapshot())
    native = set(G2_LEAF_TYPES[backend]) if backend != "headless" else {
        "Flex", "Text", "Button",
    }
    assert native <= registered
    assert "Row" not in native and "Column" not in native
    cells = [c for c in g2_certification_matrix() if c.backend == backend]
    assert {c.component for c in cells if c.status == "native"} == native | {"Flex"}


@pytest.mark.parametrize("backend", BACKENDS)
def test_every_claimed_backend_operation_has_executable_test_evidence(backend):
    source = (Path(__file__).parent / SUITES[backend]).read_text()
    for op, test in EVIDENCE[backend].items():
        assert op in OPERATIONS
        assert f"def {test}(" in source, (backend, op, test)
    # Never silently claim a borrowed native widget lifecycle is certified.
    assert "borrowed_ownership" not in EVIDENCE[backend]


def test_matrix_does_not_mistake_backend_evidence_for_per_component_closure():
    cells = g2_certification_matrix()
    assert cells
    assert all(not c.fully_certified for c in cells)
    assert all(c.pending_operations for c in cells if c.status == "native")
    assert all(set(c.pending_operations).isdisjoint(c.operations_with_evidence) for c in cells)
    assert any(c.component == "Input" and c.backend == "tk"
               and c.status == "native" for c in cells)
    assert any(c.component == "Input" and c.backend == "kivy"
               and c.status == "native" for c in cells)
    assert any(c.component == "ProgressBar" and c.backend == "kivy"
               and c.status == "native" for c in cells)
    assert any(c.component == "Checkbox" and c.backend == "kivy"
               and c.status == "native" for c in cells)
    summary = g2_matrix_summary()
    assert set(summary) == set(BACKENDS)
    assert sum(summary["qt"].values()) == len(builtin_component_registry().snapshot())


@pytest.mark.parametrize("backend", ("qt", "tk", "kivy"))
def test_c1_all_registered_native_builtins_have_explicit_sfle_geometry_port(backend):
    """C1 rejects native-UI coverage gaps; Headless negatives remain intentional.

    Transparent Fragment, delegated Native, and legacy Row/Column are tracked
    separately. This proves scope classification, NOT every C3 lifecycle cell.
    """
    cells = [cell for cell in g2_certification_matrix() if cell.backend == backend]
    assert not [cell.component for cell in cells if cell.status == "unported"]
    assert {cell.component for cell in cells if cell.status == "native"} == (
        set(G2_LEAF_TYPES[backend]) | {"Flex"}
    )


def test_c1_kivy_controls_have_intrinsic_port_without_pixel_bounds():
    from psx import Input, Checkbox, ProgressBar
    from psx.sfle.f3_native_coverage import g2_native_leaf_needs_measurement
    for constructor in (Input, Checkbox, ProgressBar):
        assert g2_native_leaf_needs_measurement(constructor(), backend="kivy")
        assert g2_native_leaf_needs_measurement(
            constructor(layout_width="84px", layout_height="24px"),
            backend="kivy",
        )


def test_component_operation_evidence_is_exact_and_traceable():
    """No stale names, missing methods, or phantom backend-level passes."""
    cells = {(cell.backend, cell.component): cell for cell in g2_certification_matrix()}
    parsed = {}
    for backend, file in COMPONENT_SUITES.items():
        source = (Path(__file__).parent / file).read_text()
        parsed[backend] = (source, ast.parse(source))
    for (backend, component, operation), method in COMPONENT_OPERATION_TESTS.items():
        assert operation in OPERATIONS
        assert operation in cells[(backend, component)].operations_with_evidence
        source, module = parsed[backend]
        functions = [
            node for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef) and node.name == method
        ]
        assert len(functions) == 1, (backend, component, operation, method)
        function = functions[0]
        content = ast.get_source_segment(source, function)
        assert content is not None
        # A literal reference to the component must be present in the actual
        # test body, including inline Kivy SDL2 subprocess scripts. Flex
        # root and the Headless probe use the public component directly.
        assert component in content, (backend, component, operation, method)

    # Every nontrivial operation lacking an explicit component reference
    # stays pending, even when there is a backend-wide reference.
    for cell in cells.values():
        certified = {
            op for op in OPERATIONS
            if (cell.backend, cell.component, op) in COMPONENT_OPERATION_TESTS
        }
        assert set(cell.operations_with_evidence) == certified
        assert set(cell.pending_operations) == set(OPERATIONS) - certified


def test_component_evidence_requires_reviewer_manifest_and_no_implicit_green():
    cells = g2_certification_matrix()
    native = [cell for cell in cells if cell.status == "native"]
    assert native
    assert all("create" in cell.operations_with_evidence for cell in native)
    assert all("borrowed_ownership" in cell.pending_operations for cell in native)
    assert all("rollback" in cell.pending_operations for cell in native)
    assert all(not cell.fully_certified for cell in native)
