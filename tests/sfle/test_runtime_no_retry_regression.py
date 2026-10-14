"""A08 native runtime errors must never trigger mid-transaction Python retry."""
import sys
from types import SimpleNamespace
import pytest
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from test_acceptance_contract_regression import case_snapshot

def test_A08_rust_runtime_failure_never_calls_python(monkeypatch):
    calls=[]
    def native_compute(_wire):
        calls.append("rust")
        raise RuntimeError("Native engine runtime panic propagated")
    fake=SimpleNamespace(
        schema_version=lambda:1,compute_json=native_compute,
        compute_provisional_json=native_compute,
    )
    monkeypatch.setitem(sys.modules,"_sfle_native",fake)
    def forbidden(self,request):
        calls.append("python")
        raise AssertionError("Unexpected fallback in the same transaction")
    monkeypatch.setattr(PythonLayoutEngine,"compute",forbidden)
    backend=load_layout_engine()
    assert backend.backend_name=="rust"
    with pytest.raises(RuntimeError,match="runtime panic"):
        backend.compute(case_snapshot("A01"))
    assert calls==["rust"]
