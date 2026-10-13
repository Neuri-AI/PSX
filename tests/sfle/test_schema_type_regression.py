"""RED A2: native schema negotiation must reject all non-integer v1 values."""

import sys
from types import SimpleNamespace

import pytest

from psx.sfle.backend import load_layout_engine
from psx.sfle.errors import DiagnosticCode, SFLEError


@pytest.mark.parametrize("reported", [True, 1.0, "1", None, 0, 2])
def test_A08_native_schema_requires_exact_integer_v1(monkeypatch, reported):
    monkeypatch.setitem(sys.modules, "_sfle_native", SimpleNamespace(
        schema_version=lambda: reported,
        compute_json=lambda value: value,
        compute_provisional_json=lambda value: value,
    ))
    with pytest.raises(SFLEError) as mismatch:
        load_layout_engine()
    assert mismatch.value.code == DiagnosticCode.BACKEND_MISMATCH
