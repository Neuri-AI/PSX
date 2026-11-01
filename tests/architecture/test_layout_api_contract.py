"""Public Cinnamon API and versioned capability contracts (Python available)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from psx.layout.contracts.capabilities import (
    EngineCapabilities, KNOWN_FEATURES, PYTHON_CAPABILITIES,
    rust_engine_capabilities,
)
from psx.layout.contracts.errors import SFLECapabilityError
from psx.layout.engine.backend import RustLayoutEngine


HISTORICAL_EXPORTS = frozenset((
    "AvailableSize", "DiagnosticCode", "EngineCapabilities", "LayoutEngine",
    "PythonLayoutEngine", "SCHEMA_VERSION", "SFLECapabilityError",
    "SFLEError", "SFLEWireError", "UnsupportedLayoutFeature",
    "dumps_input", "loads_input", "layout_input_from_wire",
    "layout_input_to_wire", "layout_result_from_wire",
    "layout_result_to_wire", "length_from_wire", "length_to_wire",
    "BoxEdges", "BoxRect", "IntrinsicSizes", "LayoutConstraints",
    "LayoutInput", "LayoutNode", "LayoutResult", "Length", "LengthKind",
    "MeasuredBox", "Rect", "WritingDirection", "parse_length",
    "ToolkitWorkerAdapter", "start_kivy_worker_layout",
    "start_tk_worker_layout",
))


def test_all_historical_root_exports_have_new_destinations():
    import psx.layout as layout
    assert HISTORICAL_EXPORTS <= set(layout.__all__)
    for name in HISTORICAL_EXPORTS:
        assert getattr(layout, name) is not None, name


def test_python_manifest_represents_bounded_kernels():
    from psx.layout.fallback.engine import PythonLayoutEngine
    actual = PythonLayoutEngine().capabilities
    assert actual == PYTHON_CAPABILITIES
    assert actual.engine_name == "python"
    assert {"grid_12_columns", "block_flow_measured",
            "inline_flow_measured", "inline_text_ltr_normal"} <= actual.certified_features


def test_rust_manifest_depends_on_real_optional_abi():
    absent = RustLayoutEngine(SimpleNamespace()).capabilities
    installed = RustLayoutEngine(SimpleNamespace(
        compute_grid_json=lambda _: None,
        compute_inline_text_json=lambda _: None,
    )).capabilities
    assert absent.engine_name == installed.engine_name == "rust"
    assert absent.status("grid_12_columns") == "unsupported"
    assert absent.status("inline_text_ltr_normal") == "unsupported"
    assert installed.status("grid_12_columns") == "certified"
    assert installed.status("inline_text_ltr_normal") == "certified"
    assert installed.status("full_bidi") == "unsupported"
    assert installed.features <= KNOWN_FEATURES
    assert installed.certified_features <= installed.features


def test_unsupported_features_fail_closed():
    manifest = rust_engine_capabilities(has_grid=True, has_inline=True)
    with pytest.raises(SFLECapabilityError):
        manifest.require("full_bidi")
    manifest.require("grid_12_columns")


def test_certification_requires_implementation():
    with pytest.raises(ValueError, match="Certified features"):
        EngineCapabilities("python", 1, frozenset(), frozenset({"gap"}))


def test_three_capability_maturity_states():
    assert PYTHON_CAPABILITIES.status("grow_shrink") == "implemented"
    assert PYTHON_CAPABILITIES.status("gap") == "certified"
    assert PYTHON_CAPABILITIES.status("full_css") == "unsupported"

def test_full_engine_modes_are_certified_for_the_bounded_contract():
    expected = (
        "full_layout_compute", "provisional_layout_compute",
        "incremental_layout_compute", "width_dependent_remeasurement",
    )
    for feature in expected:
        assert PYTHON_CAPABILITIES.status(feature) == "certified"
        assert rust_engine_capabilities(
            has_grid=True, has_inline=True,
        ).status(feature) == "certified"

def test_native_measured_flow_abi_is_negotiated_explicitly():
    from types import SimpleNamespace
    from psx.layout.engine.backend import RustLayoutEngine
    missing = RustLayoutEngine(SimpleNamespace()).capabilities
    present = RustLayoutEngine(SimpleNamespace(
        compute_measured_flow_json=lambda x: x,
    )).capabilities
    assert missing.status("measured_flow_primitives") == "unsupported"
    assert present.status("measured_flow_primitives") == "certified"
    assert PYTHON_CAPABILITIES.status("measured_flow_primitives") == "certified"

