"""N04 RED: unmeasured indefinite block percent must not silently become zero."""
import pytest
from test_acceptance_contract_regression import case_snapshot
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError,DiagnosticCode

def test_N04_unmeasured_indefinite_block_percentage_fails_closed():
    with pytest.raises(SFLEError) as raised:
        PythonLayoutEngine().compute(case_snapshot("N04"))
    assert raised.value.code==DiagnosticCode.UNSUPPORTED_FEATURE
    assert raised.value.node_id=="child"
    assert all(token in str(raised.value).lower()
               for token in ("unmeasured","indefinite","percentage","cycle"))
