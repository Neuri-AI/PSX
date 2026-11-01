"""Ensure every declared Cinnamon public operation remains available on both engines.

Private numerical helpers inside the optional Python fallback are NOT part of
this contract; platform integrations must depend on the engine-neutral API.
"""
from __future__ import annotations

import inspect

from psx.layout.contracts.engine import LayoutEngine
from psx.layout.engine.backend import RustLayoutEngine
from psx.layout.fallback.engine import PythonLayoutEngine

PUBLIC_OPERATIONS = (
    "compute",
    "compute_provisional",
    "compute_incremental",
    "compute_grid",
    "layout_inline_text",
    "layout_block_children",
    "layout_inline_atoms",
    "compute_recursive_tree",
)


def test_cinnamon_public_operations_are_implemented_by_both_backends():
    for name in PUBLIC_OPERATIONS:
        protocol = getattr(LayoutEngine, name)
        for implementation in (RustLayoutEngine, PythonLayoutEngine):
            method = getattr(implementation, name, None)
            assert callable(method), (implementation.__name__, name)
            signature = inspect.signature(method)
            declared = inspect.signature(protocol)
            assert tuple(signature.parameters) == tuple(declared.parameters), (
                implementation.__name__, name, signature, declared,
            )


def test_cinnamon_backend_identity_and_capability_contract():
    assert RustLayoutEngine.backend_name == "rust"
    assert PythonLayoutEngine.backend_name == "python"
    assert isinstance(getattr(LayoutEngine, "capabilities"), property)
    assert isinstance(getattr(RustLayoutEngine, "capabilities"), property)
    assert isinstance(getattr(PythonLayoutEngine, "capabilities"), property)
