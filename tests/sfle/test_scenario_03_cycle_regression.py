"""RED N03: do not silently resolve an unlisted indefinite percentage cycle."""
import pytest
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from test_acceptance_contract_regression import case_snapshot, _ACCEPTANCE


def test_N03_unlisted_percentage_cycle_is_classified():
    expected = _ACCEPTANCE["N03"]
    with pytest.raises(SFLEError) as error:
        PythonLayoutEngine().compute(case_snapshot("N03"))
    assert error.value.code == DiagnosticCode.UNSUPPORTED_FEATURE
    assert error.value.node_id == expected["node"]
    for token in expected["cycle_kind"].split():
        assert token.lower() in str(error.value).lower()
