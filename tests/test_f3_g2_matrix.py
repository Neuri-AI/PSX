"""Non-silent G2 registry/backend/operation coverage audit.

These tests are a census, not a claim that the G2 gate is closed.
"""
from pathlib import Path

import pytest

from psx.core.registry import builtin_component_registry
from psx.sfle.f3_native_coverage import G2_LEAF_TYPES
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
    assert any(c.component == "Input" and c.backend == "tk"
               and c.status == "unported" for c in cells)
    assert any(c.component == "ProgressBar" and c.backend == "kivy"
               and c.status == "unported" for c in cells)
    summary = g2_matrix_summary()
    assert set(summary) == set(BACKENDS)
    assert sum(summary["qt"].values()) == len(builtin_component_registry().snapshot())
