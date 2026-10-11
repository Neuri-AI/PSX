"""RED N06: unsupported CSS dependency graph must fail closed in full compute()."""
import pytest
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from test_f2_acceptance_contract_red import case_snapshot


def test_N06_indefinite_percentage_graph_refused_without_guessing_geometry():
    snapshot=case_snapshot("N06")
    with pytest.raises(SFLEError) as caught:
        PythonLayoutEngine().compute(snapshot)
    assert caught.value.code==DiagnosticCode.UNSUPPORTED_FEATURE
    assert caught.value.node_id=="child"
    assert "indefinite inline percentage padding dependency cycle" in str(caught.value).lower()
