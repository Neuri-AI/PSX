"""RED N07: unsupported CSS dependency graph must fail closed in full compute()."""
import pytest
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from test_acceptance_contract_regression import case_snapshot


def test_N07_indefinite_percentage_graph_refused_without_guessing_geometry():
    snapshot=case_snapshot("N07")
    with pytest.raises(SFLEError) as caught:
        PythonLayoutEngine().compute(snapshot)
    assert caught.value.code==DiagnosticCode.UNSUPPORTED_FEATURE
    assert caught.value.node_id=="child"
    assert "unmeasured indefinite percentage block dependency cycle" in str(caught.value).lower()
