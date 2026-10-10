"""A08 installed abi3 PyO3 wheel must compute every accepted F2 snapshot.

This file runs only in the dedicated maturin wheel job. It is intentionally
not collected in the generic SFLE Core suite (which may lack the extension).
"""
import json
from pathlib import Path

import pytest
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from test_f2_acceptance_contract_red import case_snapshot


@pytest.mark.parametrize("case_id",[
    "A01","A02","A03","A04","A05","A06","A07",
    "C01","C02","C03","C04","C05","C06","C99",
    "N01","N02","N03",
])
def test_A08_installed_pyo3_wheel_parity(case_id):
    engine=load_layout_engine()
    assert engine.backend_name=="rust", "The installed native wheel must select Rust"
    fallback=PythonLayoutEngine()
    snapshot=case_snapshot(case_id)
    if case_id in ("C99","N01","N02","N03"):
        with pytest.raises(SFLEError) as native:
            engine.compute(snapshot)
        with pytest.raises(SFLEError) as py:
            fallback.compute(snapshot)
        assert native.value.code==py.value.code==DiagnosticCode.UNSUPPORTED_FEATURE
        assert native.value.node_id==py.value.node_id
        return
    a=engine.compute(snapshot)
    b=fallback.compute(snapshot)
    assert a.generation==b.generation
    assert [node_id for node_id,_ in a.boxes]==[node_id for node_id,_ in b.boxes]
    for (_,box_a),(_,box_b) in zip(a.boxes,b.boxes):
        for name in ("content","padding","border","margin"):
            for axis in ("x","y","width","height"):
                assert getattr(getattr(box_a,name),axis)==pytest.approx(
                    getattr(getattr(box_b,name),axis),abs=0.01)
